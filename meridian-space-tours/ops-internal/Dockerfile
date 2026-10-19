FROM python:3.11-slim

# curl: healthchecks + demo payloads from the popped shell.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY seed ./seed

EXPOSE 9000

CMD ["sh", "-c", "python seed/seed.py && exec uvicorn app.main:app --host 0.0.0.0 --port 9000 --app-dir /srv"]
