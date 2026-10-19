FROM python:3.11-slim

# ping: the debug_connection tool. curl: healthchecks + demo payloads.
# bash: the /dev/tcp reverse shell. python3: PTY upgrade.
RUN apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping curl bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY web ./web
COPY seed ./seed

EXPOSE 8000

CMD ["sh", "-c", "python seed/seed.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir /srv"]
