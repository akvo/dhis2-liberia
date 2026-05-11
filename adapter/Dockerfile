FROM python:3.11-slim

WORKDIR /app

# Copy only requirements first for better caching
COPY requirements.txt .

# Copy application code
COPY . .

# Make run script executable
RUN chmod +x run.sh

# Default environment variables
ENV DHIS2_URL=http://localhost:9090/api \
    DHIS2_USERNAME=admin \
    DHIS2_PASSWORD=district \
    POLL_INTERVAL=5

# Run the worker
CMD ["./run.sh"]
