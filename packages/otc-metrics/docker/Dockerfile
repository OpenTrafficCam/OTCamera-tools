# syntax=docker/dockerfile:1
FROM debian:trixie

ENV DEBIAN_FRONTEND=noninteractive

# Debian Python packaging toolchain: pybuild + the pyproject plugin, plus the
# build backend. Swap python3-hatchling for whatever your [build-system]
# build-backend declares (see note below).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        devscripts \
        debhelper \
        dh-python \
        pybuild-plugin-pyproject \
        python3-all \
        python3-hatchling \
        fakeroot \
        lintian \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

COPY build-deb /usr/local/bin/build-deb

RUN chmod +x /usr/local/bin/build-deb

CMD ["build-deb"]
