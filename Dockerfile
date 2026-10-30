# Container image (works on Hugging Face Spaces, Fly.io, Railway or any Docker host).
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn openai python-dotenv requests
COPY mano_core.py mano_agent.py server.py ./
COPY web ./web
ENV MANO_DATA_MODE=demo PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
