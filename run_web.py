"""Web UI entrypoint for XHS content publishing.

Usage:
    python run_web.py
    # Then open http://127.0.0.1:5000
"""
import sys

from models.database import init_db
from utils.logger import setup_logger

# Import all models so Base.metadata has all tables registered
import models.content  # noqa: F401
import models.post     # noqa: F401
import models.user     # noqa: F401
from web.models import Job  # noqa: F401

setup_logger()
init_db()

from web.app import create_app
from web.worker import start_worker

start_worker()

app = create_app()

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("\n  [XHS Publish Assistant] Web UI")
    print("  Open: http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
