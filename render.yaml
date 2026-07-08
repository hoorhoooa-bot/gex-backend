services:
  - type: web
    name: gex-backend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn backend:app --host 0.0.0.0 --port $PORT
