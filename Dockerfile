# TerraGuard: the website and its API in one container (free-tier friendly: one process, small memory).
# Build:  docker build -t terraguard --build-arg DATA_URL=https://.../terraguard-data.tar.gz .
# Run:    docker run -p 10000:10000 -e DATA_URL=... terraguard      (DATA_URL is only needed if the data is not baked in)

FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
# ARROW_DEFAULT_MEMORY_POOL=system and MALLOC_ARENA_MAX=2 keep the server's memory low: measured peak 249 MB instead of 442 MB,
# which matters on a 512 MB free instance.
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 ARROW_DEFAULT_MEMORY_POOL=system MALLOC_ARENA_MAX=2
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend backend
COPY data_pipeline data_pipeline
COPY deploy/fetch_data.py deploy/start.sh deploy/
COPY data/reference data/reference
COPY --from=web /web/dist frontend/dist
ARG DATA_URL=""
ENV DATA_URL=${DATA_URL}
# If the data cannot be fetched now, the image still builds and the start-up script tries again, printing why in the logs.
RUN chmod +x deploy/start.sh && (python deploy/fetch_data.py || echo "WARNING: the data bundle was not fetched during the build; see the message above.")
ENV PORT=10000
EXPOSE 10000
CMD ["sh", "deploy/start.sh"]
