import os

# Cloud Run sends traffic to $PORT and recommends one worker with threads per vCPU.
bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
threads = int(os.environ.get("GUNICORN_THREADS", "8"))
timeout = 0
accesslog = "-"
errorlog = "-"
