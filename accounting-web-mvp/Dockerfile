# Python slim image
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && pip install gunicorn

COPY . /app

# Flask will be served by gunicorn
ENV PORT=8000
ENV GUNICORN_CMD_ARGS="--bind 0.0.0.0:${PORT} --workers 2"
CMD ["gunicorn", "app:app"]
