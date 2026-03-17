FROM ubuntu:24.04

RUN apt update && apt install -y sudo curl

RUN useradd -m -s /bin/bash borza \
    && echo 'borza:testpw' | chpasswd \
    && echo 'borza ALL=(ALL) ALL' >> /etc/sudoers

USER borza

WORKDIR /home/borza
