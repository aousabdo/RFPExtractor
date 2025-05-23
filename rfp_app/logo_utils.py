"""Helper to load application logo."""
import logging

logger = logging.getLogger(__name__)


def load_svg_logo(path: str = "rfp_analyzer_logo.svg"):
    """Return SVG logo contents.

    Raises:
        FileNotFoundError: If the logo file cannot be loaded.
    """
    try:
        with open(path, "r") as logo_file:
            return logo_file.read()
    except Exception as e:
        logger.error(f"Error loading logo: {str(e)}")
        raise
