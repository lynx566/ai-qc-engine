"""Small, portable ReportLab typography configuration."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT = "QcReportNotoSansSC"
FONT_PATH = Path(__file__).resolve().parent / "resources/fonts/NotoSansSC-Regular.ttf"
INK = colors.HexColor("#243447")
MUTED = colors.HexColor("#526172")
RULE = colors.HexColor("#D7DDE3")


def report_styles() -> dict[str, ParagraphStyle]:
    # Bundled OFL font, subset-embedded by ReportLab; no viewer/system font lookup.
    if FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT, str(FONT_PATH)))
    body = ParagraphStyle(
        "body",
        fontName=FONT,
        fontSize=10.5,
        leading=17,
        textColor=INK,
        spaceAfter=7,
        wordWrap="CJK",
        splitLongWords=True,
        allowWidows=0,
        allowOrphans=0,
    )
    return {
        "body": body,
        "title": ParagraphStyle(
            "title",
            parent=body,
            fontSize=24,
            leading=32,
            spaceAfter=14,
            keepWithNext=True,
        ),
        "section": ParagraphStyle(
            "section",
            parent=body,
            fontSize=15,
            leading=23,
            spaceBefore=16,
            spaceAfter=9,
            keepWithNext=True,
        ),
        "finding": ParagraphStyle(
            "finding",
            parent=body,
            fontSize=14,
            leading=22,
            spaceBefore=13,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=body,
            fontSize=10,
            leading=16,
            textColor=MUTED,
            spaceBefore=5,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "detail": ParagraphStyle(
            "detail",
            parent=body,
            fontSize=9.5,
            leading=15,
            textColor=MUTED,
            spaceAfter=5,
        ),
        "scope": ParagraphStyle(
            "scope",
            parent=body,
            fontSize=9.5,
            leading=14,
            leftIndent=10,
            firstLineIndent=-10,
            spaceAfter=2,
        ),
        "source_detail": ParagraphStyle(
            "source_detail",
            parent=body,
            fontSize=9.5,
            leading=15,
            textColor=MUTED,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "evidence": ParagraphStyle(
            "evidence",
            parent=body,
            leftIndent=10,
            borderColor=RULE,
            borderWidth=0.5,
            borderPadding=7,
            spaceBefore=3,
            spaceAfter=9,
        ),
        "revision": ParagraphStyle(
            "revision",
            parent=body,
            leftIndent=10,
            textColor=colors.HexColor("#255D52"),
            spaceAfter=7,
        ),
    }
