ARG BASE=ubuntu:26.04
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
        libtool \
        autoconf \
        automake \
        libssl-dev \
        libcurl4-openssl-dev \
        libboost-dev \
        libboost-system-dev \
        libboost-thread-dev \
        libboost-regex-dev \
        libboost-serialization-dev \
        libwayland-dev \
        libxkbcommon-dev \
        libx11-dev \
        libxrandr-dev \
        libxinerama-dev \
        libxcursor-dev \
        libxi-dev \
        libz-dev \
        libsqlite3-dev \
        libpcre2-dev \
        libprotobuf-dev \
        protobuf-compiler \
        libevent-dev \
        libabsl-dev \
        libbz2-dev \
        libuchardet-dev \
        librdkafka-dev \
        liblua5.4-dev \
        libgtk-3-dev \
        libmariadb-dev \
        libminiupnpc-dev \
        libleveldb-dev \
        libmaxminddb-dev \
        libsnappy-dev \
        libtbb-dev \
        libminizip-dev \
        libcivetweb-dev \
        libwxgtk3.2-dev \
        libxml2-dev \
        libtinyxml2-dev \
        libspdlog-dev \
        nlohmann-json3-dev \
        gettext \
        python3 \
        python3-pip \
        python3-venv \
        strace \
    && rm -rf /var/lib/apt/lists/*

# PCRE1 (needed by verlihub): dropped from Ubuntu 26.04, build 8.45 from source.
RUN wget -q https://downloads.sourceforge.net/project/pcre/pcre/8.45/pcre-8.45.tar.gz -O /tmp/pcre.tar.gz \
    && tar xzf /tmp/pcre.tar.gz -C /tmp \
    && cd /tmp/pcre-8.45 \
    && ./configure --quiet \
    && make -j"$(nproc)" \
    && make install \
    && ldconfig \
    && rm -rf /tmp/pcre*

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

VOLUME ["/data"]

ENTRYPOINT ["python3", "-m", "app.cli"]
CMD ["analyze"]
