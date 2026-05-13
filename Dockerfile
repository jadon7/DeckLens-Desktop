FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DECKLENS_DEVICE=cpu \
    DECKLENS_DATA_DIR=/data \
    PORT=8080

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    fonts-noto-cjk \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements.txt

COPY . .

RUN mkdir -p /data/uploads /data/outputs

EXPOSE 8080

CMD gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 600 app:app
