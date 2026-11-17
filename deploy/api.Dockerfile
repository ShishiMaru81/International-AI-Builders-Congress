FROM python:3.12-slim
WORKDIR /app
COPY apps/api/requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-ml.txt --index-url https://download.pytorch.org/whl/cpu
COPY apps/api/ ./
COPY ml/artifacts/model.json /models/model.json
COPY deploy/fetch_model.py /tmp/fetch_model.py
ENV MODEL_DIR=/models IMAGE_STORAGE_PATH=/app/storage
RUN python /tmp/fetch_model.py
RUN useradd --create-home agrosphere && mkdir -p /app/storage && chown -R agrosphere:agrosphere /app
USER agrosphere
EXPOSE 8000
CMD ["sh","-c","alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
