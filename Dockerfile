# Stage 1: Build the React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /web
COPY web/package*.json ./
RUN npm install
COPY web/ .
RUN npm run build

# Stage 2: Build the Python backend
FROM python:3.13-slim
WORKDIR /app

# Copy python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Copy the built frontend from Stage 1 into the location FastAPI expects
COPY --from=frontend-builder /web/dist ./web/dist

EXPOSE $PORT

CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--timeout", "120"]
