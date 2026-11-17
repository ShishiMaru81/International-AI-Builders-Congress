FROM python:3.12-slim
WORKDIR /app
ENV MULTICROP_MODEL_DIR=/models/multicrop
COPY requirements*.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-ml.txt --index-url https://download.pytorch.org/whl/cpu
COPY . .
RUN useradd --create-home agrosphere && mkdir -p /app/storage && chown -R agrosphere:agrosphere /app
USER agrosphere
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
