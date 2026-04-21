FROM python:3.11-slim

WORKDIR /app

# No native libs needed — pypdf is pure Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure runtime dirs exist
RUN mkdir -p uploads generated_games

ENV PORT=8080

EXPOSE 8080

CMD ["gunicorn", "app:app", "-c", "gunicorn.conf.py"]
