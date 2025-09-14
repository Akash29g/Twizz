# ---- Base image ----
FROM python:3.11-slim

# ---- Set work directory ----
WORKDIR /app

# ---- Install system dependencies ----
# We need tesseract-ocr + image libs
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    pkg-config \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Install Python dependencies ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Copy project files ----
COPY . .

# ---- Run the bot ----
CMD ["python", "scraper.py"]
