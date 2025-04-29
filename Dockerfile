# Use official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt
COPY requirements.txt /app/

# Upgrade pip and setuptools
RUN pip install --upgrade pip setuptools wheel

# Install Python dependencies
RUN pip install -r requirements.txt

# Copy the application code
COPY . /app/

# Expose the port the app runs on
EXPOSE 5000

# Set the entrypoint to run the Flask app
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
