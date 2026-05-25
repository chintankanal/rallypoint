#!/bin/sh

# Start the Python backend on internal port 8001
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8001 &

# Start Caddy (it will proxy /api to 8001 and serve static files)
caddy run --config ./Caddyfile --adapter caddyfile