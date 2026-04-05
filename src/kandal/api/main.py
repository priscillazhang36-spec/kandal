import logging

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from kandal.api.landing import LANDING_HTML
from kandal.api.routes import auth, matches, profiles

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Kandal", version="0.1.0")
app.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
app.include_router(matches.router, prefix="/matches", tags=["matches"])
app.include_router(auth.router, tags=["auth"])


@app.get("/", response_class=HTMLResponse)
def landing():
    return LANDING_HTML


@app.get("/health")
def health():
    return {"status": "ok"}
