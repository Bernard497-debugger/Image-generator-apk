# Use a slim Python image for a smaller footprint
FROM python:3.11-slim

# Install system dependencies for Pillow and high-quality fonts
RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Create and set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose the port Flask/Gunicorn will run on
EXPOSE 10000

# Start the application using Gunicorn
# Using --bind 0.0.0.0:$PORT allows Render to inject its dynamic port
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-10000}"]