FROM python:3.12-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r docker_requirements.txt

ENV FLASK_APP=app.py

CMD gunicorn -b 0.0.0.0:$PORT app:app
