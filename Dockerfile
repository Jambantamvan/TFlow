# TFlow - Dockerfile
# Cross-distribution containerized hardware manager for gaming laptops

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    make \
    git \
    python3-tk \
    tk-dev \
    pciutils \
    libx11-6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/build-afc
RUN git clone --depth 1 https://github.com/Keyitdev/asus-fan-control-ec.git . && \
    make clean && make && \
    cp asus-fan-control-ec /usr/local/bin/ && \
    chmod 4755 /usr/local/bin/asus-fan-control-ec && \
    rm -rf /tmp/build-afc

WORKDIR /app

COPY backend.py gui.py main.py README.md ./
COPY windows_bin/ ./windows_bin/

RUN chmod +x /app/main.py

CMD ["python3", "/app/main.py"]
