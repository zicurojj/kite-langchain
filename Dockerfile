FROM python:3.10-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7860 5001

# Create necessary directories
RUN mkdir -p /app/data /app/logs

CMD ["python", "mcp_server.py"]
