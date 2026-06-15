FROM python:3.11-slim as builder

WORKDIR /app

# Install system compilation dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into a virtualenv/local path or user directory
RUN pip install --no-cache-dir --user -r requirements.txt

# Final production stage
FROM python:3.11-slim

# Create system user & group to avoid running as root
RUN groupadd -g 10001 orbitgroup && \
    useradd -u 10001 -g orbitgroup -m -s /bin/bash orbituser

WORKDIR /home/orbituser/app

# Set production environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PATH="/home/orbituser/.local/bin:${PATH}"

# Install curl in final image for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed site-packages from builder stage
COPY --from=builder --chown=orbituser:orbitgroup /root/.local /home/orbituser/.local
COPY --chown=orbituser:orbitgroup . .

# Use non-root user
USER orbituser

EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
