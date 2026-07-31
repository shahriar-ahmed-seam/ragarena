# syntax=docker/dockerfile:1

# ---------- build ----------------------------------------------------------
FROM python:3.12-slim AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
RUN pip install --no-cache-dir hatchling

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip wheel --no-deps --wheel-dir /wheels .

# ---------- runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    RAGARENA_CACHE_DIR=/data/cache \
    HF_HOME=/data/models

# Non-root by default. The image only ever reads a corpus and writes results,
# so it has no reason to run privileged.
RUN useradd --create-home --uid 10001 arena \
    && mkdir -p /data/cache /data/models /work/results \
    && chown -R arena:arena /data /work

COPY --from=build /wheels /wheels
# `local` brings in fastembed so the image can run with no API keys at all.
RUN pip install --no-cache-dir /wheels/*.whl "fastembed>=0.4" \
    && rm -rf /wheels

WORKDIR /work
USER arena
VOLUME ["/data", "/work/results"]

# Fail fast on a broken image rather than at the end of a benchmark.
HEALTHCHECK --interval=1m --timeout=20s --start-period=5s --retries=2 \
    CMD ragarena validate --dataset meridian || exit 1

ENTRYPOINT ["ragarena"]
CMD ["bench", "--suite", "quick", "--no-judge", \
     "--embed-provider", "fastembed", "--rerank-provider", "crossencoder", \
     "--out", "/work/results"]
