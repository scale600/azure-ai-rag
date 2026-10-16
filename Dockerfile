FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/app.py api/rag.py api/ingest.py ./
COPY data/ ./data/

ENV DATA_DIR=/app/data \
    PORT=8000

EXPOSE 8000

CMD ["gunicorn", "--bind=0.0.0.0:8000", "--timeout", "600", "--workers", "1", "app:app"]
