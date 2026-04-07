import logging

import sentry_sdk
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from kandal.api.landing import LANDING_HTML
from kandal.api.legal import PRIVACY_HTML, TERMS_HTML
from kandal.api.routes import auth, chat, matches, profiles
from kandal.core.config import get_settings

logging.basicConfig(level=logging.INFO)

_settings = get_settings()
if _settings.sentry_dsn:
    sentry_sdk.init(
        dsn=_settings.sentry_dsn,
        traces_sample_rate=0.0,
        send_default_pii=False,
    )

app = FastAPI(title="Kandal", version="0.1.0")
app.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
app.include_router(matches.router, prefix="/matches", tags=["matches"])
app.include_router(auth.router, tags=["auth"])
app.include_router(chat.router, tags=["chat"])


@app.get("/", response_class=HTMLResponse)
def landing():
    return LANDING_HTML


@app.get("/privacy", response_class=HTMLResponse)
def privacy():
    return PRIVACY_HTML


@app.get("/terms", response_class=HTMLResponse)
def terms():
    return TERMS_HTML


@app.get("/health")
def health():
    return {"status": "ok"}
