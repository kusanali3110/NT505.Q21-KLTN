FROM python:3.11-slim
WORKDIR /app
COPY services/alert-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip "wheel>=0.46.2" "jaraco.context>=6.1.0" && \
    pip install --no-cache-dir -r requirements.txt
COPY services/alert-service/main.py ./main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
