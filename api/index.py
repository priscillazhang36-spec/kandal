"""Vercel serverless entry point — re-exports the FastAPI app."""

import sys
from pathlib import Path

# Add src/ to Python path so kandal package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from kandal.api.main import app  # noqa: E402
