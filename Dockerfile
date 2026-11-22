FROM python:3.12-slim-bookworm
ARG TARGETARCH
ARG TECTONIC_VERSION=0.15.0
ENV PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/opt/playwright JOBFORGE_DATA=/data
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl nodejs fontconfig libfontconfig1 libssl3 && rm -rf /var/lib/apt/lists/*
RUN set -eu; \
    case "$TARGETARCH" in \
      arm64) target=aarch64-unknown-linux-musl ;; \
      amd64|"") target=x86_64-unknown-linux-musl ;; \
      *) exit 1 ;; \
    esac; \
    curl --fail --location --retry 3 "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-${target}.tar.gz" -o /tmp/tectonic.tar.gz; \
    tar -xzf /tmp/tectonic.tar.gz -C /usr/local/bin tectonic; \
    rm /tmp/tectonic.tar.gz

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && python -m playwright install --with-deps chromium
RUN useradd --create-home --uid 10001 jobforge && mkdir /data && chown jobforge:jobforge /data
COPY . .
USER jobforge
RUN python -m jobforge.resumes
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn jobforge.api:app --host 0.0.0.0 --port 8000"]
