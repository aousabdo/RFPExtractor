"""Helper to load application logo."""
import os
import logging

logger = logging.getLogger(__name__)


def load_svg_logo(path: str = "rfp_analyzer_logo.svg"):
    """Return SVG logo contents.

    The logo path can be overridden with the ``LOGO_PATH`` environment
    variable.

    Raises:
        FileNotFoundError: If the logo file cannot be loaded.
    """
    logo_path = os.getenv("LOGO_PATH", path)
    try:
        with open(logo_path, "r") as logo_file:
            return logo_file.read()
    except Exception as e:
        logger.error(f"Error loading logo: {str(e)}")
        raise
