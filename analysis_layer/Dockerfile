FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
# Install build tools required for some Python packages (like webrtcvad)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8083
CMD ["uvicorn", "init:app", "--host", "0.0.0.0", "--port", "8083"]