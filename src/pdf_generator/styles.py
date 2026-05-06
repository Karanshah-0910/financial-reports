"""
styles.py
---------
All colors, fonts, and spacing for the report.
Change values here to rebrand for any client.
"""

from reportlab.lib import colors
from reportlab.lib.units import inch

# ---------------------------------------------------------------------------
# Brand colors
# ---------------------------------------------------------------------------
COLOR_NAVY       = colors.HexColor("#1B2A4A")   # Headers, cover background
COLOR_ACCENT     = colors.HexColor("#2E86AB")   # Highlights, table header
COLOR_LIGHT_BLUE = colors.HexColor("#EAF4FB")   # Alternating table rows
COLOR_GREEN      = colors.HexColor("#27AE60")   # Positive numbers
COLOR_RED        = colors.HexColor("#E74C3C")   # Negative / down numbers
COLOR_WHITE      = colors.white
COLOR_BLACK      = colors.HexColor("#1A1A1A")
COLOR_LIGHT_GRAY = colors.HexColor("#F5F5F5")
COLOR_MID_GRAY   = colors.HexColor("#CCCCCC")

# ---------------------------------------------------------------------------
# Spacing
# ---------------------------------------------------------------------------
PAGE_MARGIN      = 0.75 * inch
SECTION_GAP      = 0.25 * inch
ROW_HEIGHT       = 0.28 * inch
