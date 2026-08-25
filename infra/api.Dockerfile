FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps/api ./apps/api
RUN pip install --no-cache-dir . && playwright install --with-deps chromium

EXPOSE 8000
CMD ["uvicorn", "agentprobe.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000"]
