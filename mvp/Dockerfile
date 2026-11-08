FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Hugging Face Spaces expects port 7860. Set GROQ_API_KEY as a Space secret.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]
