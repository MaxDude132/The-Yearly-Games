#!/bin/sh
# Runs once before each Railway deploy goes live (railway.toml: preDeployCommand).
# Updates the tables, then loads the game content (safe to repeat: rows are updated, not duplicated).
set -e

python manage.py migrate --noinput
python manage.py load_content
