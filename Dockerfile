FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including ping and speedtest
RUN apt-get update && apt-get install -y \
    iputils-ping \
    curl \
    gnupg \
    && curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | bash \
    && apt-get install -y speedtest \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application files
COPY network_monitor.py .
COPY network_api.py .
COPY weather_tracker.py .
COPY dashboard.html .
COPY .env .

# Create startup script
RUN echo '#!/bin/bash\n\
python -u weather_tracker.py &\n\
python -u network_monitor.py 2>&1 &\n\
gunicorn -w 2 -b 0.0.0.0:5000 network_api:app\n\
' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 5000

CMD ["/app/start.sh"]
