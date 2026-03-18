FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files (Unfold CSS/JS, admin assets)
RUN DJANGO_SETTINGS_MODULE=settings.base \
    SECRET_KEY=collectstatic-placeholder \
    POSTGRES_HOST=placeholder \
    python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000
