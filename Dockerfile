FROM node:22-alpine AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NLTK_DATA=/usr/local/share/nltk_data

RUN addgroup --system voiceagent && adduser --system --ingroup voiceagent voiceagent
WORKDIR /app

COPY pyproject.toml requirements.lock ./
COPY --chown=voiceagent:voiceagent src/ ./src/
COPY --chown=voiceagent:voiceagent configs/runtime/ ./configs/runtime/
COPY --chown=voiceagent:voiceagent --from=frontend-builder /build/frontend/dist ./frontend/dist/

RUN pip install -r requirements.lock
RUN python -m nltk.downloader -d /usr/local/share/nltk_data punkt_tab

# Named-volume target for the bot database; ownership survives first mount.
RUN mkdir -p /data && chown voiceagent:voiceagent /data

USER voiceagent
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
