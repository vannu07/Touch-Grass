FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY lastlight ./lastlight
COPY web ./web
COPY data ./data
COPY tests ./tests

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "lastlight.app:app", "--host", "0.0.0.0", "--port", "8000"]
