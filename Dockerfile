FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONPATH=/app
ENV DRY_RUN=true
ENV TARGET_PLATFORM=threads
ENV LOG_LEVEL=INFO

CMD ["python", "-m", "src.cli", "run-mvp", "--limit", "5"]
