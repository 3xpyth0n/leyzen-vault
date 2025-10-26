# orchestrator/Dockerfile
FROM python:3.11-alpine

WORKDIR /app

RUN apk add --no-cache docker-cli curl

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "vault_orchestrator.py"]
