"""Gunicorn settings for the production image. Gunicorn reads this file from the working directory."""

import os

wsgi_app = "config.wsgi:application"
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"  # Railway sets PORT
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
accesslog = "-"
errorlog = "-"
# The control socket (a local admin channel, new in gunicorn 27) is not used here.
control_socket_disable = True
# Railway's proxy sets X-Forwarded-* headers; it is the only thing that can reach the container.
forwarded_allow_ips = "*"
