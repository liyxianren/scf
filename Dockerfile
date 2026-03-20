FROM python:3.11-slim-bookworm

# Keep the image small for Zeabur builds; handbook Mermaid export already
# falls back to mermaid.ink when local mmdc/chromium is unavailable.
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Default port (Zeabur will override with $PORT)
ENV PORT=8080
EXPOSE 8080

# Run with gunicorn using shell form to expand $PORT
CMD gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300
