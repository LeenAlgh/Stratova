"""Load company brand identity from beam_data_brand_identity.pdf."""

import base64
import os

import fitz  # PyMuPDF

from project_paths import ASSETS_DIR, BRAND_LOGO_PNG, KB_DOCS_DIR

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = str(KB_DOCS_DIR)
DEFAULT_BRAND_IDENTITY_PDF = "beam_data_brand_identity.pdf"
LOGO_FILENAME = "beam_data_logo.png"

BEAM_DATA_VISUAL_SYSTEM = {
    "essence": (
        "Practical AI transformation partner for enterprises. "
        "Optimistic, clear, warm, collaborative, enterprise-credible."
    ),
    "colors": [
        {"name": "Primary Navy", "hex": "#1E2660", "role": "primary"},
        {"name": "Deep Navy", "hex": "#1B1A4D", "role": "primary"},
        {"name": "Coral/Pink", "hex": "#D6356E", "role": "accent"},
        {"name": "Hot Pink", "hex": "#E8366E", "role": "accent"},
        {"name": "Peach", "hex": "#F7A77E", "role": "accent"},
        {"name": "Warm Gold", "hex": "#E8B584", "role": "accent"},
        {"name": "Deep Plum", "hex": "#4C2766", "role": "secondary"},
        {"name": "Magenta Plum", "hex": "#B22D6B", "role": "secondary"},
        {"name": "Page BG", "hex": "#F8F7FB", "role": "background"},
    ],
    "typography": {
        "primary": "Poppins",
        "fallback": ["Liberation Sans", "Noto Sans"],
        "style": "Rounded geometric sans-serif",
    },
    "logo": {
        "description": (
            "Official navy capital B with four triangular blades in "
            "peach, pink, magenta, and plum. Do not redraw for production."
        ),
        "gradient": "Warm gold → coral/pink → deep navy/plum (footer, CTAs, banners)",
    },
    "ui_style": "Rounded white cards, thin grey borders, light SaaS-consulting feel.",
    "avoid": "Dark cyber look, orange beam motif, generic AI hype, impossible promises.",
}


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ")
    return " ".join(text.split())


def load_brand_identity(pdf_path: str | None = None) -> dict:
    """
    Extract full brand identity text from the brand identity PDF.

    Returns:
        dict with doc_id, page_count, formatted, source_path
    """
    path = pdf_path or os.path.join(DOCS_DIR, DEFAULT_BRAND_IDENTITY_PDF)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Brand identity PDF not found at {path}. "
            f"Place {DEFAULT_BRAND_IDENTITY_PDF} in knowledge_base/documents/."
        )

    doc_id = os.path.basename(path)
    doc = fitz.open(path)
    pages = []
    for page_num in range(len(doc)):
        text = _clean_text(doc[page_num].get_text())
        if text:
            pages.append(f"[Page {page_num + 1}]\n{text}")

    formatted = "\n\n".join(pages)
    return {
        "doc_id": doc_id,
        "page_count": len(doc),
        "formatted": formatted,
        "source_path": path,
    }


def ensure_logo_extracted(pdf_path: str | None = None) -> str:
    """Return brand logo PNG path, extracting from PDF into 03_assets if needed."""
    logo_path = str(BRAND_LOGO_PNG)
    if os.path.exists(logo_path):
        return logo_path

    path = pdf_path or os.path.join(DOCS_DIR, DEFAULT_BRAND_IDENTITY_PDF)
    doc = fitz.open(path)
    if len(doc) == 0:
        return logo_path

    images = doc[0].get_images(full=True)
    if not images:
        return logo_path

    xref = images[0][0]
    image = doc.extract_image(xref)
    BRAND_LOGO_PNG.parent.mkdir(parents=True, exist_ok=True)
    with open(logo_path, "wb") as f:
        f.write(image["image"])
    return logo_path


def get_logo_base64(pdf_path: str | None = None) -> str | None:
    logo_path = ensure_logo_extracted(pdf_path)
    if not os.path.exists(logo_path):
        return None
    with open(logo_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def get_visual_system(pdf_path: str | None = None) -> dict:
    """Structured brand identity for UI display."""
    identity = load_brand_identity(pdf_path)
    logo_path = ensure_logo_extracted(pdf_path)
    visual = dict(BEAM_DATA_VISUAL_SYSTEM)
    visual["doc_id"] = identity["doc_id"]
    visual["page_count"] = identity["page_count"]
    visual["logo"]["filename"] = LOGO_FILENAME if os.path.exists(logo_path) else None
    visual["logo"]["available"] = os.path.exists(logo_path)
    return visual
