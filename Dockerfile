FROM node:22-bookworm-slim AS node_runtime
FROM python:3.13-slim-bookworm
ENV PYTHONUNBUFFERED=1 NO_BROWSER=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py index.html ./
RUN useradd --create-home appuser && mkdir /app/downloads && chown appuser:appuser /app/downloads
USER appuser
CMD ["python", "app.py"]
