from pathlib import Path

APP_NAME = "Methodica"
APP_VERSION = "1.0.0"
SECRET_KEY = "methodica-dev-secret-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "storage"
UPLOADS = STORAGE / "uploads"
REPORTS = STORAGE / "reports"
CHARTS = STORAGE / "charts"
EXPORTS = STORAGE / "exports"
SAMPLE_DATA = BACKEND_DIR / "sample_data"
DB_PATH = STORAGE / "methodica.db"

for p in (STORAGE, UPLOADS, REPORTS, CHARTS, EXPORTS, SAMPLE_DATA):
    p.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

MAX_UPLOAD_MB = 80
MAX_PREVIEW_ROWS = 200
MAX_PROFILE_ROWS = 250_000
