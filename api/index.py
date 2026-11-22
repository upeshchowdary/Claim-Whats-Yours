import os
import sys
from pathlib import Path

# Add backend and backend/src to path
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

try:
    engine = make_engine(get_settings().database_url)
    Base.metadata.create_all(bind=engine)
    from scripts.seed_database import seed_database
    seed_database()
except Exception as err:
    print("[Vercel Startup] DB setup notice:", err)

app = create_app()
