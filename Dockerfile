# ================================================================
# FILE: Dockerfile
# PURPOSE: Package entire project into a container
#
# THINK OF IT AS: A recipe that tells HuggingFace
#   exactly how to build and run your environment
#
# WHY PYTHON 3.11:
#   Stable version
#   Compatible with all our libraries
#   Recommended for FastAPI projects
#
# WHY PORT 7860:
#   HuggingFace Spaces uses 7860 by default
#   Any other port = deployment fails!
# ================================================================

# Start with official Python 3.11 image
# slim = smaller size, faster to download
FROM python:3.11-slim

# ================================================================
# SET WORKING DIRECTORY
# All commands run from this folder inside container
# ================================================================
WORKDIR /app

# ================================================================
# INSTALL SYSTEM DEPENDENCIES
# Some Python libraries need system packages
# Install these before Python packages
# ================================================================
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ================================================================
# COPY REQUIREMENTS FIRST
# We copy requirements.txt before other files
# Why? Docker caches layers
# If requirements dont change, this layer is cached
# Makes rebuilding much faster!
# ================================================================
COPY requirements.txt .

# ================================================================
# INSTALL PYTHON DEPENDENCIES
# --no-cache-dir = dont save pip cache
#                  keeps container smaller
# ================================================================
RUN pip install --no-cache-dir -r requirements.txt

# ================================================================
# COPY ALL PROJECT FILES
# The dot means copy everything from current folder
# into /app inside container
# ================================================================
COPY . .

# ================================================================
# SET ENVIRONMENT VARIABLES
# These are defaults inside container
# HuggingFace Secrets will override HF_TOKEN and others
# ================================================================
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ================================================================
# EXPOSE PORT
# Tell Docker this container uses port 7860
# MUST be 7860 for HuggingFace Spaces!
# ================================================================
EXPOSE 7860

# ================================================================
# HEALTH CHECK
# Docker periodically checks if container is healthy
# Pings our root endpoint every 30 seconds
# If it fails 3 times container is marked unhealthy
# ================================================================
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:7860/health')" \
    || exit 1

# ================================================================
# START COMMAND
# This runs when container starts
# uvicorn = the server that runs FastAPI
# host 0.0.0.0 = accept requests from anywhere
# port 7860 = HuggingFace required port
# workers 1 = single worker fits in 2vcpu 8gb limit
# ================================================================
CMD ["uvicorn", "app.main:app", \
    "--host", "0.0.0.0", \
    "--port", "7860", \
    "--workers", "1"] 