# ---- Base image ----
FROM python:3.11-slim

# ---- Set work directory ----
WORKDIR /app

# ---- Install system dependencies ----
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    pkg-config \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Set Tesseract path environment variable ----
ENV TESSERACT_CMD=/usr/bin/tesseract

# ---- Install Python dependencies ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Copy project files ----
COPY . .

# ---- Run the bot ----
CMD ["python", "-u", "scraper.py"]

