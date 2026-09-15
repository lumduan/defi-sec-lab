# Hooks image for defi-sec-lab: pre-commit + detect-secrets (hash-pinned) + gitleaks (checksum-verified).
# Built on demand by scripts/hooks-image.sh and used by .githooks/*, so nothing is installed on the host.
# Every input is pinned: base image by digest, Python packages by hash, gitleaks by sha256.
FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# gitleaks v8.30.1 (linux x64). sha256 from the release's gitleaks_8.30.1_checksums.txt.
ADD --checksum=sha256:551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb \
    https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz \
    /tmp/gitleaks.tar.gz
RUN tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks \
 && rm /tmp/gitleaks.tar.gz \
 && gitleaks version

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt

# The repo is bind-mounted and owned by the invoking host user (the container runs as that uid):
# trust it without per-user git config. /cache holds pre-commit's hook environments (named volume).
RUN git config --system --add safe.directory '*' \
 && mkdir -p /cache \
 && chmod 1777 /cache
ENV PRE_COMMIT_HOME=/cache/pre-commit \
    HOME=/tmp
