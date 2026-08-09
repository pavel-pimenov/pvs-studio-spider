# 24.04 chosen because the official ubuntu:26.04 tag was broken (exec format
# error) when this image was authored; bump to 26.04 once the tag is fixed.
ARG BASE=ubuntu:24.04
FROM ${BASE}

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED=1

# System toolchain needed to build the analyzed C/C++ projects.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        wget \
        gnupg \
        git \
        build-essential \
        cmake \
        ninja-build \
        pkg-config \
        bear \
        python3 \
        python3-pip \
        python3-venv \
        strace \
    && rm -rf /var/lib/apt/lists/*

# PVS-Studio (Linux) from the official repository.
RUN wget -qO- https://wcdn.pvs-studio.com/etc/pubkey.txt \
        | gpg --dearmor -o /etc/apt/trusted.gpg.d/viva64.gpg \
    && wget -O /etc/apt/sources.list.d/viva64.list \
        https://wcdn.pvs-studio.com/etc/viva64.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends pvs-studio \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

ENV PATH="/opt/venv/bin:$PATH"
COPY app /app/app
COPY projects.yaml /app/projects.yaml

RUN mkdir -p /data/src /data/work /data/reports

WORKDIR /app

ENV SPIDER_SRC_DIR=/data/src
ENV SPIDER_WORK_DIR=/data/work
ENV SPIDER_REPORTS_DIR=/data/reports
ENV SPIDER_JOBS=4

VOLUME ["/data"]

ENTRYPOINT ["python3", "-m", "app.cli"]
CMD ["analyze"]
