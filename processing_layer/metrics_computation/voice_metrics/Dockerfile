# Can't use small base image due to praat-parselmouth library installation
FROM python:3.11-bullseye

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    ninja-build \
    libsndfile1-dev \
    python3-dev \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN cmake --version

RUN pip install --upgrade pip
RUN pip install scikit-build
RUN pip install --no-cache-dir --no-build-isolation praat-parselmouth

# CPU-only torch. This layer uses torch for Silero VAD and resemblyzer speaker
# embeddings -- both CPU workloads -- so the default CUDA build (~3GB of unused GPU
# libraries) is replaced with the CPU wheel. resemblyzer's torch dependency below is
# then satisfied by this pre-installed build.
RUN pip install --no-cache-dir torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
# Drop praat-parselmouth (installed above) and the CUDA/torch tree (CPU torch is
# pre-installed; the GPU libraries are dead weight on a CPU/edge node).
RUN grep -vEi "praat-parselmouth|^torch|^torchaudio|^triton|^nvidia-|^cuda-|^sympy|^networkx|^mpmath" requirements.txt > temp_requirements.txt
RUN pip install --no-cache-dir -r temp_requirements.txt

RUN apt-get update && apt-get install -y praat

ENV PYTHONPATH="/app/core/myprosody"

WORKDIR /app
COPY . .

CMD ["python", "-u", "init.py"]