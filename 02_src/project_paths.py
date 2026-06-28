"""Central path layout for the sratovazip project."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "01_data"
ASSETS_DIR = PROJECT_ROOT / "03_assets"

OUTPUTS_DIR = DATA_DIR / "outputs"
OUTPUT_RUNS_DIR = OUTPUTS_DIR / "runs"
DATASET_DIR = DATA_DIR / "dataset"
KB_DOCS_DIR = DATA_DIR / "knowledge_base" / "documents"
CHROMA_DIR = KB_DOCS_DIR / "chroma_db"
SRC_DIR = Path(__file__).resolve().parent
ENV_PATH = SRC_DIR / ".env"

UI_LOGO_SVG = ASSETS_DIR / "ui" / "logo.svg"
UI_STYLE_CSS = ASSETS_DIR / "ui" / "style.css"
BRAND_LOGO_PNG = ASSETS_DIR / "beam_data_logo.png"

# Code root — used for imports and agent modules
ROOT_DIR = SRC_DIR
