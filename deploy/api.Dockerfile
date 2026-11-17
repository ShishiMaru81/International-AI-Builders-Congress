FROM python:3.12-slim AS doctor-export
WORKDIR /build
COPY apps/api/requirements-ml.txt /tmp/requirements-ml.txt
RUN pip install --no-cache-dir -r /tmp/requirements-ml.txt --index-url https://download.pytorch.org/whl/cpu
COPY ml/doctor/requirements-export.txt /tmp/requirements-export.txt
RUN pip install --no-cache-dir -r /tmp/requirements-export.txt
COPY scripts/install_doctor_models.py scripts/install_doctor_models.py
COPY apps/api/app/doctor_catalog.json apps/api/app/doctor_catalog.json
RUN python scripts/install_doctor_models.py --output /models/multicrop

FROM python:3.12-slim
WORKDIR /app
COPY apps/api/requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-ml.txt --index-url https://download.pytorch.org/whl/cpu
COPY apps/api/ ./
COPY ml/artifacts/model.json /models/model.json
COPY deploy/fetch_model.py /tmp/fetch_model.py
COPY --from=doctor-export /models/multicrop /models/multicrop
ENV MODEL_DIR=/models MULTICROP_MODEL_DIR=/models/multicrop IMAGE_STORAGE_PATH=/app/storage
RUN python /tmp/fetch_model.py
RUN useradd --create-home agrosphere && mkdir -p /app/storage && chown -R agrosphere:agrosphere /app
USER agrosphere
EXPOSE 8000
CMD ["sh","-c","alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
