FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=7860
ENV WORKERS=2

EXPOSE 7860

CMD ["sh", "-c", "uvicorn server.app:app --host $HOST --port $PORT --workers $WORKERS"]
