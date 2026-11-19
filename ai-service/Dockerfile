FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements-service.txt .
RUN pip install --no-cache-dir --default-timeout=600 --retries 10 torch==2.15.0+cpu --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple \
    && pip install --no-cache-dir -r requirements-service.txt

COPY dp_ml ./dp_ml
COPY service ./service
COPY models ./models

EXPOSE 8001
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8001"]
