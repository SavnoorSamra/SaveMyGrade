FROM node:20-bullseye

WORKDIR /app

# Python runtime for Flask backend.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install backend deps first for better layer caching.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /app/backend/requirements.txt

# Install frontend deps.
COPY frontend/package.json frontend/package-lock.json /app/frontend/
RUN cd /app/frontend && npm ci

# Copy full repo (including scraped data and course catalog).
COPY . /app

# Start script launches backend + frontend dev server in one container.
COPY docker/start.sh /usr/local/bin/start.sh
RUN chmod +x /usr/local/bin/start.sh

ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=5050
ENV VITE_API_PROXY_TARGET=http://localhost:5050

EXPOSE 5050 5173

CMD ["/usr/local/bin/start.sh"]
