# Use official Python slim image
FROM python:3.11-slim

# Install system dependencies for Pillow
RUN apt-get update && \
    apt-get install -y libjpeg-dev zlib1g-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Set working directory
WORKDIR /app

# Copy your app code
COPY . /app

# Install Python dependencies
RUN pip install -r requirements.txt

# Expose port for Render
ENV PORT 5000

# Start the app using Gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:$PORT"]
