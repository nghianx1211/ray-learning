FROM python:3.10-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# Cài đặt wget cho health checks
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip \
 && pip install ray[serve]==2.35.0 fastapi uvicorn

COPY fake_llm_app.py /app/fake_llm_app.py