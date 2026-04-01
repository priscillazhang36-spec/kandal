from fastapi import FastAPI

from kandal.api.routes import auth, matches, profiles

app = FastAPI(title="Kandal", version="0.1.0")
app.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
app.include_router(matches.router, prefix="/matches", tags=["matches"])
app.include_router(auth.router, tags=["auth"])


@app.get("/health")
def health():
    return {"status": "ok"}
