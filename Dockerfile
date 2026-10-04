# Backend (FastAPI + WebSocket) for Railway/Render. Build context = project root.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY research/src research/src
COPY research/reports research/reports
COPY backend backend
WORKDIR /app/backend
ENV OMP_NUM_THREADS=1 \
    PCOOL_MODEL=lstm:models_subset/SUBSET104_L0_lstm/model.pt \
    PCOOL_REPORTS=/app/research/reports \
    PCOOL_REPLAY_PACK=/tmp/pcool/replay_pack.parquet
# replay data is NOT shipped: it is built at startup from the public S3 files in replay_jobs.json
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
