FROM hub.intra.doublefs.com/sys/baseimage/python:3.9
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
ARG PIP
ENV PIP_INDEX_URL ${PIP}
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Create log directory
RUN mkdir -p /var/log/django

# Expose port
EXPOSE 8000

# Use startup script
CMD ["./start.sh"] 