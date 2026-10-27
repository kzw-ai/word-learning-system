# Backend Dockerfile for Flask API
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app_phase.py .
COPY adaptive_engine.py .
COPY auth.py .
COPY user_data_isolation.py .
COPY models_extended.py .
COPY confusable_api.py .
COPY words_extended.db .
COPY data/ ./data/
COPY learning_materials/ ./learning_materials/
# app_phase 启动时从 scripts/ 加载课件题目同步与示范数据脚本
COPY scripts/ ./scripts/

# Expose Flask port
EXPOSE 5004

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5004/api/stats')" || exit 1

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5004", "--workers", "2", "--timeout", "120", "app_phase:app"]
