FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.local/bin:/root/.cargo/bin:${PATH}"
# Canonical layout: SYNC_ROOT defaults to $HOME/synced via .vars. No env overrides.

RUN apt-get update && apt-get install -y sudo curl git make stow && \
    rm -rf /var/lib/apt/lists/* && \
    echo 'root ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers && \
    rm -f /root/.profile

WORKDIR /root/synced/composites/pkm/diencephalon
COPY . .

RUN make install-uv

# base: real install (apt-base, restow, rust, rclone). shell + dev: dry-run.
RUN make setup-run PROFILES= && \
    make setup-dry-run PROFILES="shell dev" && \
    make setup-verify PROFILES= && \
    make setup-list
