FROM python:3.11-slim
WORKDIR /app
COPY services/user-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/user-service/main.py ./main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
