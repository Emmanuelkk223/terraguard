#!/bin/sh
# Container entry point: fetch the data if it is not baked into the image, then serve the site and the API.
python deploy/fetch_data.py || echo "data download failed; starting anyway"
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
