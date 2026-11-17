FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng libgomp1 openssl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.lock /app/requirements.lock
RUN pip install -r requirements.lock
COPY pyproject.toml /app/
COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/
RUN pip install --no-deps . && useradd --uid 10001 --create-home documind && mkdir -p /data/documents /data/models && chown -R documind:documind /data
USER 10001:10001
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "64", "--no-access-log", "--no-proxy-headers"]
