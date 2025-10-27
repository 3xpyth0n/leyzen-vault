FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY proxy.py ./

EXPOSE 2375

CMD ["gunicorn", "--bind", "0.0.0.0:2375", "--workers", "2", "--threads", "4", "proxy:app"]
