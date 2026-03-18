FROM python:3.11-slim

# Install gcc for C code compilation, Node.js for mermaid-cli, and Chromium for puppeteer
RUN apt-get update && apt-get install -y \
    gcc \
    libc6-dev \
    nodejs \
    npm \
    chromium \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    && rm -rf /var/lib/apt/lists/*

# Install mermaid-cli globally
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
RUN npm install -g @mermaid-js/mermaid-cli

WORKDIR /app
ENV REFRESHED_AT=2024-01-14

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Initialize database
RUN python init_db.py

# Default port (Zeabur will override with $PORT)
ENV PORT=8080
EXPOSE 8080

# Run with gunicorn using shell form to expand $PORT
CMD gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300
