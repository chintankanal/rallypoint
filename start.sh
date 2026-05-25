#!/bin/sh

# Exit immediately if any command fails
set -e

echo "Starting Gunicorn/Uvicorn backend on port 8001..."
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8001 &

echo "Starting Caddy server on port $PORT..."
# 'exec' replaces the shell script process with Caddy, allowing Caddy to receive OS signals directly
exec caddy run --config ./Caddyfile --adapter caddyfile