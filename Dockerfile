FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p output

EXPOSE 8000

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MAX_CONCURRENCY=2

CMD ["python", "server.py"] 