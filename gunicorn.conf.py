# Gunicorn configuration
bind = "0.0.0.0:5000"
workers = 1
timeout = 600  # 10 minutes - needed for slow AI API calls (especially dual-model)
graceful_timeout = 300  # Grace period for worker shutdown
