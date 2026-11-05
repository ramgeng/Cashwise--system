# Cashwise: one container that builds the React app and serves it from FastAPI.

# ---- 1. build the frontend
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. the backend, with the built site in frontend/dist
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY scripts/ scripts/
COPY data/ data/
COPY --from=web /web/dist frontend/dist
# accounts and uploaded data live here; mount a disk at this path to keep them
ENV CASHWISE_STORAGE=/srv/storage
RUN mkdir -p /srv/storage
EXPOSE 8000
# Render sets PORT; locally it falls back to 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
