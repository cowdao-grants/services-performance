# CoW Performance Testing Suite Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    POETRY_VERSION=2.3.2 \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Add Poetry to PATH
ENV PATH="$POETRY_HOME/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry and export plugin
RUN pip install poetry==${POETRY_VERSION} poetry-plugin-export

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock* README.md ./

# Export locked dependencies and install via pip (respects PIP_DEFAULT_TIMEOUT)
RUN poetry export --without-hashes --only main -f requirements.txt -o /tmp/requirements.txt && \
    pip install --timeout 300 -r /tmp/requirements.txt

# Copy application code
COPY src/ ./src/
COPY configs/ ./configs/

# Install the application
RUN poetry install --only-root

# Create directory for results
RUN mkdir -p /app/results /app/.cow-perf

# Set the entrypoint
ENTRYPOINT ["cow-perf"]

# Default command shows help
CMD ["--help"]
