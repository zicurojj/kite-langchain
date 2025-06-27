FROM python:3.10-slim

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080 3000

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Create startup script
COPY start_droplet.sh /app/start_droplet.sh
RUN chmod +x /app/start_droplet.sh

CMD ["/app/start_droplet.sh"]
