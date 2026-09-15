# learn-api: FastAPI inspector. Base pinned by digest; dependencies installed with --require-hashes; non-root.
FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin inspector

COPY --chmod=0755 entrypoint.sh /usr/local/bin/inspector-entrypoint
COPY inspector ./inspector

USER 10001
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/inspector-entrypoint"]
