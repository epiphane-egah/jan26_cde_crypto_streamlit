FROM python:3.13-slim

# Installer cron
RUN apt-get update \
    && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

# Copier ton projet
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Configurer le cron
COPY cronjob /etc/cron.d/my-cron
RUN chmod 0644 /etc/cron.d/my-cron \
    && crontab /etc/cron.d/my-cron

# Lancer cron au premier plan
# CMD ["streamlit", "run", "app.py", "--server.port", "8080", "--server.address", "0.0.0.0"]
CMD streamlit run app.py --server.port=$PORT --server.address=0.0.0.0