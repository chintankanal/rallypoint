# Stage 1: Build the React frontend using Railway's recommended Node image
FROM node:lts-alpine AS build
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
ENV NPM_CONFIG_FUND=false
WORKDIR /app
COPY web/package*.json ./
RUN npm ci --legacy-peer-deps
COPY web/ ./
RUN npm run build

# Stage 2: Build the Python backend and final image
FROM python:3.13-slim
WORKDIR /app

# Install Caddy to serve the React app and proxy API requests
RUN apt-get update && apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl \
    && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg \
    && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list \
    && apt-get update && apt-get install -y caddy \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Copy the built frontend and Caddyfile
COPY --from=build /app/dist ./dist
COPY Caddyfile ./
RUN caddy fmt Caddyfile --overwrite

# Railway handles the external $PORT. Internal Gunicorn will run on 8001.
ENV PORT=8000
EXPOSE $PORT

# Copy the start script and ensure it is executable
COPY start.sh ./
RUN chmod +x start.sh

CMD ["/app/start.sh"]
