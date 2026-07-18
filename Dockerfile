# syntax=docker/dockerfile:1.7
FROM python:3.12.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels .

FROM python:3.12.11-slim-bookworm AS runtime

ARG PIKI_UID=10001
ARG PIKI_GID=10001
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIKI_HOST=0.0.0.0 \
    PIKI_PORT=8000

RUN groupadd --gid ${PIKI_GID} piki \
    && useradd --uid ${PIKI_UID} --gid piki --create-home --shell /usr/sbin/nologin piki \
    && install -d -o piki -g piki /var/run/piki /app

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels
COPY --chown=piki:piki alembic.ini ./
COPY --chown=piki:piki migrations ./migrations

USER piki
EXPOSE 8000
STOPSIGNAL SIGTERM
CMD ["piki-api"]

