FROM python:3.12-slim

WORKDIR /app
COPY services/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/api/app ./services/api/app

CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "8200"]
