FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY servidor_lento ./servidor_lento
COPY celery_app ./celery_app

# Forma exec: python es el PID 1 y recibe SIGTERM directamente
CMD ["python", "-m", "app.main"]
