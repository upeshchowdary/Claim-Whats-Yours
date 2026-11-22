import os
import sys
from pathlib import Path
from starlette.types import ASGIApp, Scope, Receive, Send
from fastapi import APIRouter, Request

# Setup paths
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
backend_src = root_dir / "backend" / "src"
backend_dir = root_dir / "backend"

for p in (str(backend_src), str(backend_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Serverless writable database path
if not os.environ.get("DATABASE_URL"):
    tmp_db_path = Path("/tmp/claim_whats_yours.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db_path.as_posix()}"

from claim_whats_yours.core.config import get_settings
from claim_whats_yours.db.base import Base
from claim_whats_yours.db.session import make_engine
from claim_whats_yours.main import create_app
from claim_whats_yours.api.v1.endpoints import (
    admin,
    assistant,
    eligibility,
    health,
    meta,
    schemes,
    tracking,
)

# Initialize database schema and seeds
try:
    engine = make_engine(get_settings().database_url)
    Base.metadata.create_all(bind=engine)
    from scripts.seed_database import seed_database
    seed_database()
except Exception as err:
    print("[Vercel Startup] DB setup notice:", err)

app = create_app()

class VercelPathRewriteMiddleware:
    """Restores original request path from x-matched-path or x-forwarded-path on Vercel."""
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            for name, value in scope.get("headers", []):
                lower_name = name.lower()
                if lower_name in (b"x-matched-path", b"x-vercel-matched-path", b"x-forwarded-path"):
                    matched_path = value.decode("latin-1").split("?")[0]
                    if matched_path and matched_path not in ("/api/index", "/api"):
                        scope["path"] = matched_path
                        break
        await self.app(scope, receive, send)

app.add_middleware(VercelPathRewriteMiddleware)

# Also register /v1 prefix for environments where /api is stripped by routing proxies
v1_alt = APIRouter(prefix="/v1")
v1_alt.include_router(meta.router)
v1_alt.include_router(schemes.router)
v1_alt.include_router(eligibility.router)
v1_alt.include_router(assistant.router)
v1_alt.include_router(tracking.router)
v1_alt.include_router(admin.router)
app.include_router(v1_alt)

# Health alternative paths
@app.get("/live")
def live_alt():
    return {"status": "ok"}

@app.get("/")
def debug_root(request: Request):
    return {
        "status": "ok",
        "path": request.url.path,
        "scope_path": request.scope.get("path"),
        "headers": dict(request.headers),
    }
