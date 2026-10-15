FROM python:3.12-slim
WORKDIR /app
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api/app ./app
COPY data ./data
ENV DEMO_DATA_DIR=/app/data/demo
ENV PYTHONUNBUFFERED=1
RUN useradd --create-home digest && chown -R digest:digest /app
USER digest
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
