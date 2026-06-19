# DocuMind API

Run locally with Python 3.12: create a virtual environment with `python3.12 -m venv .venv`, activate it (`source .venv/bin/activate`), install the project in editable mode with the dev extras via `pip install -e '.[dev]'`, then start the server with `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`. The app exposes `GET /api/health/live` (always 200) and `GET /api/health/ready` (200 when the database and `vector` extension are reachable, 503 otherwise); it imports and starts even without a database present. Run the test suite with `pytest`.
