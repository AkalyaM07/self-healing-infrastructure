# Multi-capability DevOps Self-Healing Container (Python FastAPI + Ansible + Docker Engine Client)
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies, Ansible, and Docker CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    openssh-client \
    ca-certificates \
    gnupg \
    lsb-release \
    procps \
    ansible \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI so Ansible can inspect and restart containers via /var/run/docker.sock
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && apt-get install -y --no-install-recommends docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*

# Install Ansible Community Docker collection
RUN ansible-galaxy collection install community.docker

# Set working directory
WORKDIR /app

# Install Python requirements
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend, frontend, ansible playbooks, and configs
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY ansible/ /app/ansible/

# Create runtime directories
RUN mkdir -p /app/database /app/logs

# Set environment variables
ENV DATABASE_PATH=/app/database/self_healing.db
ENV FRONTEND_DIR=/app/frontend
ENV ANSIBLE_DIR=/app/ansible
ENV PROMETHEUS_URL=http://prometheus:9090
ENV ALERTMANAGER_URL=http://alertmanager:9093
ENV NGINX_CHECK_URL=http://nginx:80

EXPOSE 8000

# Health check for backend
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
