import os
import sys
from pathlib import Path
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

# Initialize database schema and seeds
try:
    engine = make_engine(get_settings().database_url)
    Base.metadata.create_all(bind=engine)
    from scripts.seed_database import seed_database
    seed_database()
except Exception as err:
    print("[Vercel Startup] DB setup notice:", err)

app = create_app()

dist_dir = (root_dir / "frontend" / "dist").resolve()
assets_dir = dist_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

@app.get("/index.html")
def get_index():
    return FileResponse(dist_dir / "index.html")

@app.get("/")
def get_root():
    return FileResponse(dist_dir / "index.html")

@app.get("/{full_path:path}")
def catch_all(full_path: str):
    target = dist_dir / full_path
    if full_path and target.is_file():
        return FileResponse(target)
    return FileResponse(dist_dir / "index.html")
