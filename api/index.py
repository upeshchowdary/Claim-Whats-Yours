import os
import sys
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

@app.get("/ready")
def ready_alt():
    return {"status": "ready", "database": "ok"}

# Serve frontend build if routed to this function
dist_dir = (root_dir / "frontend" / "dist").resolve()
assets_dir = dist_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    file_path = dist_dir / full_path
    if full_path and file_path.is_file():
        return FileResponse(file_path)
    index_file = dist_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"status": "ok", "app": "Claim What's Yours"}
