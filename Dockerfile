FROM python:3.11-slim

WORKDIR /app

# Ensure Python can find all backend modules (data/, intelligence/, etc.)
ENV PYTHONPATH=/app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Create persistent data directory for SQLite
RUN mkdir -p /data

EXPOSE 8000

# Single worker keeps memory low on Railway free tier
CMD ["sh", "-c", "python3 -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --timeout-keep-alive 75"]
