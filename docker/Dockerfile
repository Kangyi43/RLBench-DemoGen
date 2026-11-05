FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates wget xz-utils \
        python3 python3-pip python3-dev \
        xvfb libgl1-mesa-dri libglu1-mesa libglx-mesa0 libegl-mesa0 \
        libosmesa6 mesa-utils \
        libx11-6 libx11-xcb1 libxext6 libxrender1 libxcb1 \
        libxcb-glx0 libxcb-xinerama0 libxcb-xkb1 libxcb-icccm4 \
        libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
        libxcb-shape0 libxkbcommon-x11-0 libfontconfig1 libfreetype6 \
        libxcursor1 libdbus-1-3 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ARG COPPELIASIM_URL=https://downloads.coppeliarobotics.com/V4_1_0/CoppeliaSim_Player_V4_1_0_Ubuntu20_04.tar.xz
COPY docker/coppeliasim.tar.xz /tmp/coppeliasim.tar.xz
RUN mkdir -p /opt/coppeliasim \
    && tar -xJf /tmp/coppeliasim.tar.xz -C /opt/coppeliasim --strip-components=1 \
    && rm /tmp/coppeliasim.tar.xz \
    && ln -sf /opt/coppeliasim/libcoppeliaSim.so /opt/coppeliasim/libcoppeliaSim.so.1

ENV COPPELIASIM_ROOT=/opt/coppeliasim \
    LD_LIBRARY_PATH=/opt/coppeliasim:/opt/coppeliasim/platforms \
    QT_QPA_PLATFORM_PLUGIN_PATH=/opt/coppeliasim/platforms \
    QT_PLUGIN_PATH=/opt/coppeliasim

ARG PIP_INDEX_URL=
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel \
    && pip3 install --no-cache-dir "numpy<2" Pillow cffi pyquaternion scipy natsort gymnasium \
       fastapi "uvicorn[standard]" pyyaml pandas "pyarrow>=14" av

ARG PYREP_REPO=https://github.com/stepjam/PyRep
ARG PYREP_REF=master
ARG GIT_DEPTH=1
ARG GITHUB_MIRROR=
RUN export GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIMEOUT=30; \
    depth="--depth ${GIT_DEPTH}"; [ "${GIT_DEPTH}" = "0" ] && depth=""; \
    for i in 1 2 3 4 5; do \
        git clone ${depth} "${GITHUB_MIRROR}${PYREP_REPO}" /opt/PyRep && break; \
        echo "clone attempt $i failed, retrying..."; rm -rf /opt/PyRep; sleep $((i * 3)); \
    done \
    && cd /opt/PyRep && git checkout "${PYREP_REF}" \
    && pip3 install --no-cache-dir --no-build-isolation /opt/PyRep

ARG RLBENCH_REPO=https://github.com/stepjam/RLBench
ARG RLBENCH_REF=master
RUN export GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIMEOUT=30; \
    depth="--depth ${GIT_DEPTH}"; [ "${GIT_DEPTH}" = "0" ] && depth=""; \
    for i in 1 2 3 4 5; do \
        git clone ${depth} "${GITHUB_MIRROR}${RLBENCH_REPO}" /opt/RLBench && break; \
        echo "clone attempt $i failed, retrying..."; rm -rf /opt/RLBench; sleep $((i * 3)); \
    done \
    && cd /opt/RLBench && git checkout "${RLBENCH_REF}"

ENV PYTHONPATH=/opt/RLBench:/app

COPY tasks_extra/tasks/ /opt/RLBench/rlbench/tasks/
COPY tasks_extra/task_ttms/ /opt/RLBench/rlbench/task_ttms/

WORKDIR /app
COPY scripts/ /app/scripts/
COPY web/ /app/web/
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh \
    && python3 -c "import sys; sys.path.insert(0, '/app/web'); from main import app; print('web app import OK')"

ENV DEMOGEN_DATA=/data \
    DEMOGEN_SCRIPTS=/app/scripts \
    DEMOGEN_CONFIGS=/configs \
    LIBGL_ALWAYS_SOFTWARE=1

EXPOSE 8000
WORKDIR /data
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["serve"]
