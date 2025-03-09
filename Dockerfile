# Use the official Python image as the base image
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev

RUN apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY . /app/

WORKDIR /app

RUN python3 -m venv /opt/venv
RUN . /opt/venv/bin/activate && pip install --upgrade pip
RUN . /opt/venv/bin/activate && pip install -r requirements.txt

EXPOSE 3838

# # Set the entrypoint to activate the virtual environment and run the shiny command
ENTRYPOINT ["/bin/sh", "-c", ". /opt/venv/bin/activate && exec shiny run --reload app.py --host 0.0.0.0 --port 3838"]