"""UCO-Sensor — Report generators (HTML + SVG badge)."""
from .html_report import generate_html_report
from .badge import generate_badge_svg, badge_color

__all__ = ["generate_html_report", "generate_badge_svg", "badge_color"]
