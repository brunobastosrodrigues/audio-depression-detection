FROM python:3.9-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# CPU-only torch (resemblyzer runs speaker embeddings on CPU); avoids the ~3GB CUDA
# build. resemblyzer's torch dependency in requirements is satisfied by this.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "init:app", "--host", "0.0.0.0", "--port", "8000"]
