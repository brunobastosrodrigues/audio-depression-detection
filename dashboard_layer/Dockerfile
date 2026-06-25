FROM python:3.10-slim

# Install system dependencies for audio processing and resemblyzer
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# CPU-only torch (used by the optional resemblyzer voice-enrollment feature, CPU only);
# avoids the ~3GB CUDA build. Its torch dependency in requirements is satisfied by this.
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8084
CMD ["streamlit", "run", "Home.py", "--server.port=8084", "--server.address=0.0.0.0"]
