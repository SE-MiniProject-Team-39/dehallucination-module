FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ ./backend/
COPY --from=frontend /build/dist ./frontend/dist
RUN useradd --create-home dam && chown -R dam:dam /app
USER dam
EXPOSE 8000
CMD ["uvicorn", "backend.dam.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
