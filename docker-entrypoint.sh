#!/bin/sh
# Starts as root only to give the app user the photo folder: a Railway volume is mounted owned
# by root. Then runs the command (gunicorn by default) as the app user.
set -e

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DJANGO_MEDIA_ROOT"
    chown app:app "$DJANGO_MEDIA_ROOT"
    exec setpriv --reuid=app --regid=app --init-groups -- "$@"
fi

exec "$@"
