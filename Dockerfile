FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements-google.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-google.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
