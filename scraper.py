import os
import requests
import pytesseract
import asyncio
import discord
import random
import re
import json
from instagrapi import Client
from instagrapi.exceptions import LoginRequired
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
TARGET_USER = os.getenv("TARGET_USER")
SESSION_FILE = "session.json"
DOWNLOAD_DIR = "stories"
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# allow overriding tesseract path via env (only needed on weird hosts)
TESSERACT_CMD = os.getenv("TESSERACT_CMD")
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
# otherwise pytesseract will use the system-installed tesseract (what we install in Docker)

print("[DEBUG] DISCORD_TOKEN present:", bool(DISCORD_TOKEN))

# --------------Blocklist-------------------

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

BLOCKLIST = ["lmao", "lol","lmk","imo","tysm","stress","type something...",
             "imk","dumb","wanna", "sudo", "zero", "sorry", "replied","zero2sudo","proud","congrats","dm'd","dm","dms","mistake","before i post them."]

cl = Client()

# --- Discord client ---
intents = discord.Intents.default()
client = discord.Client(intents=intents)



# --- Seen Stories ---
SEEN_FILE = "seen.json"

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


# ---------------- IG LOGIN ----------------
def login_client(force=False):
    if not force and os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.get_timeline_feed()  # test if session works
            print("[+] Logged in using saved session")
            return
        except Exception as e:
            print(f"[!] Saved session invalid: {e}")

    # Fresh login
    cl.login(IG_USERNAME, IG_PASSWORD)
    cl.dump_settings(SESSION_FILE)
    print("[+] Fresh login and session saved")


def force_relogin():
    try:
        cl.logout()
    except Exception:
        pass
    login_client(force=True)


def safe_get_user_id(username: str):
    try:
        return cl.user_info_by_username_v1(username).pk  # ✅ private API only
    except LoginRequired:
        print("[!] Login required during story fetch. Re-logging once...")
        login_client(force=True)
        return cl.user_info_by_username_v1(username).pk


# ---------------- OCR CLEAN ----------------
def extract_text_from_image(image_path):
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    merged_lines = []
    buffer = ""
    for line in lines:
        if buffer:
            buffer += " " + line
        else:
            buffer = line

        if buffer.endswith((".", "?", "!", ":", ";")):
            merged_lines.append(buffer.strip())
            buffer = ""

    if buffer:
        merged_lines.append(buffer.strip())

    return "\n".join(merged_lines)



# ---------------- DISCORD ----------------
async def send_discord_message(text, image_path=None):
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print("[!] Discord channel not found!")
        return

    # Create embed
    embed = discord.Embed(
        title="🌟New Update",
        description=text if text else "No text detected",
        color=0x5865F2  # Discord blurple
    )

    if image_path:
        # Attach image and display it inside the embed
        file = discord.File(image_path, filename="story.jpg")
        embed.set_image(url="attachment://story.jpg")
        await channel.send(embed=embed, file=file)
    else:
        # Just send embed with text
        await channel.send(embed=embed)



# ---------------- STORY FETCH ----------------
def download_image(url, path):
    resp = requests.get(url, stream=True)
    if resp.status_code == 200:
        with open(path, "wb") as f:
            f.write(resp.content)
        return True
    return False


async def check_stories():
    seen = load_seen()
    try:
        user_id = safe_get_user_id(TARGET_USER)
        stories = cl.user_stories(user_id)

        if not stories:
            print("[DEBUG] No new stories, continuing...")
            return
        print(f"[DEBUG] Found {len(stories)} stories")

        for story in stories:
            if story.pk in seen:
                print(f"[SKIP] Already posted story {story.pk}")
                continue

            filename = os.path.join(DOWNLOAD_DIR, f"{story.pk}.jpg")
            if download_image(story.thumbnail_url, filename):
                print(f"[+] Downloaded: {filename}")
                text = extract_text_from_image(filename)
                # Normalize OCR text
                normalized_text = (
                text.lower()
                .replace("’", "'")
                .replace("‘", "'")
                .replace("…", "...")    
                .strip()
                )
                normalized_blocklist = [w.lower().replace("…", "...").strip() for w in BLOCKLIST]
                matched = [word for word in normalized_blocklist if word in normalized_text]
                if matched:
                    if ".com" not in normalized_text:  
                        print(f"[SKIP] Blocklist word(s) {matched} found in {story.pk}: {text}")
                        continue

                print(f"[OCR Result]\n{text}\n{'-'*40}")
                await send_discord_message(text, filename)

                # Delete the image after posting
                if os.path.exists(filename):
                    os.remove(filename)
                    print(f"[+] Deleted image: {filename}")

                # ✅ Mark as seen
                seen.add(story.pk)
                save_seen(seen)

    except LoginRequired:
        print("[!] Login required during story fetch. Skipping this cycle.")



# ---------------- LOOP ----------------
async def story_loop():
    while True:
        print("\n--- Checking stories ---")
        await check_stories()
        print("Sleeping for some minutes...\n")
        await asyncio.sleep(random.randint(270, 550))

# ---------------- MAIN ----------------
@client.event
async def on_ready():
    print(f"[+] Discord bot logged in as {client.user}")
    login_client()

    # ✅ Keep images, no deletion
    asyncio.create_task(story_loop())

client.run(DISCORD_TOKEN)
