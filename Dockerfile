FROM python:3.12-slim

# Шрифты, чтобы matplotlib красиво рисовал кириллицу
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot

# Данные (БД и фото) монтируются как volume в /data
ENV DB_PATH=/data/pushups.db \
    PHOTO_DIR=/data/photos \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "bot.main"]
