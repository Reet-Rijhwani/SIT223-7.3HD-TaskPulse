
# Updated Python 3.12 base image using Debian Trixie
FROM python:3.12-slim-trixie

# Set the application working directory
WORKDIR /srv

# Create a dedicated non-root application user
# and a persistent database directory
RUN useradd --uid 10001 --create-home appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data

# Copy the application source code
COPY app ./app

# Run the application without root privileges
USER appuser

# Application environment configuration
ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DB_PATH=/data/tasks.db

# Expose the application port
EXPOSE 8000

# Verify that the application is healthy
HEALTHCHECK --interval=15s \
    --timeout=3s \
    --start-period=5s \
    --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"

# Start the TaskPulse application
CMD ["python", "-m", "app.server"]