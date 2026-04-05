import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from kandal.api.routes import auth, matches, profiles

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Kandal", version="0.1.0")
app.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
app.include_router(matches.router, prefix="/matches", tags=["matches"])
app.include_router(auth.router, tags=["auth"])

def _find_landing_page() -> str:
    """Search for public/index.html from multiple possible roots."""
    import os
    # Walk up from this file and from cwd to find public/index.html
    roots = [
        Path(__file__).resolve().parents[3],  # src/kandal/api -> project root
        Path(os.getcwd()),
        Path("/var/task"),
    ]
    for root in roots:
        candidate = root / "public" / "index.html"
        if candidate.exists():
            return candidate.read_text()
    return "<h1>kandal</h1><p>Coming soon.</p>"


LANDING_HTML = _find_landing_page()


@app.get("/", response_class=HTMLResponse)
def landing():
    return LANDING_HTML


@app.get("/health")
def health():
    return {"status": "ok"}
