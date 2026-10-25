# Linux toolchain for running `make check` on a Mac: periph needs SocketCAN, i2c-dev and
# libgpiod v2, none of which exist on macOS. Mirrors the apt steps of .github/workflows/ci.yml.
# Native arm64 on Apple Silicon (an amd64-emulated container proves nothing, see AGENTS.md).
# Used by `make docker-check`; not a CI image.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
        ca-certificates git sudo cmake g++ make pkg-config meson ninja-build \
        python3 python3-pip clang-format \
    && pip install --break-system-packages -q lizard \
    && rm -rf /var/lib/apt/lists/*

# Same script CI runs; sudo is needed by its final `ninja install`.
COPY ci/install-libgpiod-v2.sh /tmp/install-libgpiod-v2.sh
RUN bash /tmp/install-libgpiod-v2.sh && rm /tmp/install-libgpiod-v2.sh

# The repo is bind-mounted from the host with a foreign owner; git refuses it otherwise.
RUN git config --system --add safe.directory '*'
WORKDIR /repo
