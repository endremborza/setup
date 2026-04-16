FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y python3 python3-pip curl git && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/setup-pkg
COPY setup/ ./setup/
COPY pyproject.toml ./

# Smoke test: dry-run levels 0 and 1 — verifies the package imports and step registration
RUN python3 -m setup run --level 0 --dry-run
RUN python3 -m setup run --level 1 --dry-run
RUN python3 -m setup list
