FROM python:3.11-slim

# Install gcc for C code compilation
RUN apt-get update && apt-get install -y \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

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
CMD gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120
