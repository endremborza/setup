FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
ENV HOME=/root
ENV USER=root
ENV PATH="/root/.local/bin:/root/.cargo/bin:${PATH}"
# Canonical layout: SYNC_ROOT defaults to $HOME/synced via .vars. No env overrides.

RUN apt-get update && apt-get install -y sudo curl git make stow && \
    rm -rf /var/lib/apt/lists/* && \
    echo 'root ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Place the diencephalon checkout under the canonical synced tree.
WORKDIR /root/synced/composites/pkm/diencephalon
COPY . .

# Ubuntu's stock /root/.profile would conflict with the stow symlink restow creates.
RUN rm -f /root/.profile

RUN make install-uv

# base profile: real install (apt-base, restow, rust, rclone)
RUN make setup-run PROFILES=
# shell + dev: dry-run only (cheap; just validates step registration)
RUN make setup-dry-run PROFILES="shell dev"
RUN make setup-verify PROFILES=
RUN make setup-list
