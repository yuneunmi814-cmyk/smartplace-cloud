FROM python:3.12-slim

WORKDIR /app

# psycopg (binary) is added here so the container can talk to PostgreSQL
# while local dev/test stays on SQLite.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "psycopg[binary]>=3.2"

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
