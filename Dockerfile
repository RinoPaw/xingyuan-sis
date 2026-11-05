FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XINGYUAN_HOME=/data \
    XINGYUAN_DB_PATH=/data/xingyuan.db \
    XINGYUAN_DEMO_MODE=0 \
    HOST=0.0.0.0 \
    PORT=3000

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . gunicorn \
    && useradd --uid 10001 --user-group --create-home xingyuan \
    && mkdir -p /data && chown xingyuan:xingyuan /data

USER xingyuan
VOLUME ["/data"]
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/healthz')" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "xingyuan_sis.web:create_app()"]
