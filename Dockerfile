# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install uv for faster dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY lucidnews ./lucidnews
COPY data ./data
COPY profiles ./profiles
COPY .env.example .env.example

# Install optional extras from a comma-separated list, e.g. "twitter".
ARG EXTRAS=""
RUN set -eu; \
    set --; \
    if [ -n "$EXTRAS" ]; then \
        case "$EXTRAS" in ,*|*,|*,,*) echo "Invalid EXTRAS list: $EXTRAS" >&2; exit 2 ;; esac; \
        old_ifs=$IFS; IFS=,; \
        for extra in $EXTRAS; do \
            case "$extra" in [._-]*|*[._-]|*[!A-Za-z0-9._-]*) echo "Invalid extra: $extra" >&2; exit 2 ;; esac; \
            set -- "$@" --extra "$extra"; \
        done; \
        IFS=$old_ifs; \
    fi; \
    uv sync --frozen --no-dev "$@"

# Runtime data is mounted here; keep the image and process unprivileged.
RUN useradd --create-home --uid 10001 lucidnews \
    && mkdir -p /data \
    && chown -R lucidnews:lucidnews /app /data

# Create volume mount points
VOLUME ["/app/data", "/data"]

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
USER lucidnews

# Run the application
ENTRYPOINT ["uv", "run", "lucidnews"]
CMD []
