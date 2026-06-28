"""UI configuration."""

from project_paths import UI_LOGO_SVG

LOGO_SVG_PATH = UI_LOGO_SVG

BRAND_BLUE = "#1d348a"
LIGHT_GREY = "#f1f1f1"

GTM_BRIEF_FIELDS = ["product", "audience", "market", "goals"]


def load_logo_svg() -> str:
    return LOGO_SVG_PATH.read_text(encoding="utf-8")
