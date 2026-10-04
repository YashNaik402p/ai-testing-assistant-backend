import io
import os
import re

from fastapi.responses import StreamingResponse

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from xml.sax.saxutils import escape


def download_pdf(project,doc,file_info_flag,source=None):
    """
    Convert generated Markdown documentation into a formatted PDF.

    Handles:
    - Unicode characters
    - #, ##, ### headings
    - **bold**
    - *italic*
    - ***bold italic***
    - `inline code`
    - bullet lists
    - numbered lists
    - Markdown tables
    - --- horizontal separators
    - Markdown formatting inside tables
    """

    # =========================================================
    # 1. Locate DejaVu fonts
    # =========================================================

    base_dir = os.path.dirname(os.path.abspath(__file__))
    # font_path=os.path.join(base_dir, "fonts",)
    regular_font = os.path.join(
        base_dir,"fonts",
        "DejaVuSans.ttf"
    )

    bold_font = os.path.join(
        base_dir,"fonts",
        "DejaVuSans-Bold.ttf"
    )

    italic_font = os.path.join(
        base_dir,"fonts",
        "DejaVuSans-Oblique.ttf"
    )

    bold_italic_font = os.path.join(
        base_dir,"fonts",
        "DejaVuSans-BoldOblique.ttf"
    )

    # Register fonts
    pdfmetrics.registerFont(
        TTFont("DejaVuSans", regular_font)
    )

    pdfmetrics.registerFont(
        TTFont("DejaVuSans-Bold", bold_font)
    )

    pdfmetrics.registerFont(
        TTFont("DejaVuSans-Oblique", italic_font)
    )

    pdfmetrics.registerFont(
        TTFont("DejaVuSans-BoldOblique", bold_italic_font)
    )

    # =========================================================
    # 2. Create PDF
    # =========================================================
    file_name=project.project_name.strip().replace(" ","_").lower()
    pdf_file = io.BytesIO()

    document = SimpleDocTemplate(
        pdf_file,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"{file_name} Documentation",
    )

    # =========================================================
    # 3. PDF styles
    # =========================================================

    title_style = ParagraphStyle(
        "PDFTitle",
        fontName="DejaVuSans-Bold",
        fontSize=20,
        leading=25,
        alignment=TA_LEFT,
        spaceAfter=12,
    )

    heading1_style = ParagraphStyle(
        "Heading1",
        fontName="DejaVuSans-Bold",
        fontSize=16,
        leading=20,
        spaceBefore=12,
        spaceAfter=8,
    )

    heading2_style = ParagraphStyle(
        "Heading2",
        fontName="DejaVuSans-Bold",
        fontSize=14,
        leading=18,
        spaceBefore=10,
        spaceAfter=6,
    )

    heading3_style = ParagraphStyle(
        "Heading3",
        fontName="DejaVuSans-Bold",
        fontSize=12,
        leading=16,
        spaceBefore=8,
        spaceAfter=5,
    )

    normal_style = ParagraphStyle(
        "Normal",
        fontName="DejaVuSans",
        fontSize=9.5,
        leading=14,
        spaceAfter=5,
    )

    bullet_style = ParagraphStyle(
        "Bullet",
        parent=normal_style,
        leftIndent=12,
        firstLineIndent=-7,
        spaceAfter=4,
    )

    numbered_style = ParagraphStyle(
        "Numbered",
        parent=normal_style,
        leftIndent=15,
        firstLineIndent=-15,
        spaceAfter=4,
    )

    table_style = ParagraphStyle(
        "Table",
        fontName="DejaVuSans",
        fontSize=8,
        leading=11,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        fontName="DejaVuSans-Bold",
        fontSize=8,
        leading=11,
    )

    code_style = ParagraphStyle(
        "Code",
        fontName="DejaVuSans",
        fontSize=8.5,
        leading=12,
    )

    # =========================================================
    # 4. Markdown inline formatting
    # =========================================================

    def format_inline(text):
        """
        Convert Markdown inline formatting to ReportLab markup.

        Supports:
        - `inline code`
        - **bold**
        - ***bold italic***
        - *italic*
        """

        # Escape characters that have special meaning in ReportLab XML
        text = escape(str(text))

        # ---------------------------------------------------------
        # Protect inline code first
        # ---------------------------------------------------------

        code_parts = []

        def protect_code(match):
            code_text = match.group(1)

            placeholder = f"@@CODE_{len(code_parts)}@@"

            code_parts.append(code_text)

            return placeholder

        text = re.sub(
            r"`([^`]+)`",
            protect_code,
            text
        )

        # ---------------------------------------------------------
        # Bold + italic
        # ---------------------------------------------------------

        text = re.sub(
            r"\*\*\*(.+?)\*\*\*",
            r"<b><i>\1</i></b>",
            text
        )

        # ---------------------------------------------------------
        # Bold
        # ---------------------------------------------------------

        text = re.sub(
            r"\*\*(.+?)\*\*",
            r"<b>\1</b>",
            text
        )

        # ---------------------------------------------------------
        # Italic
        # ---------------------------------------------------------

        text = re.sub(
            r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)",
            r"<i>\1</i>",
            text
        )

        # ---------------------------------------------------------
        # Restore inline code
        # ---------------------------------------------------------

        for index, code_text in enumerate(code_parts):

            placeholder = f"@@CODE_{index}@@"

            safe_code = escape(code_text)

            replacement = (
                f"<font name='DejaVuSans'>{safe_code}</font>"
            )

            text = text.replace(
                placeholder,
                replacement
            )

        return text

    # =========================================================
    # 5. Markdown table helper
    # =========================================================

    def is_table_separator(line):
        """
        Detect Markdown table separator:

        |------|-------------|
        |------|-------------|
        """

        cells = [
            cell.strip()
            for cell in line.strip("|").split("|")
        ]

        if not cells:
            return False

        for cell in cells:
            if not re.fullmatch(r":?-+:?", cell):
                return False

        return True

    def create_table(table_data):
        """
        Convert Markdown table data into a ReportLab table.
        """

        if not table_data:
            return None

        # Remove separator rows
        cleaned_rows = [
            row
            for row in table_data
            if not is_table_separator(
                "|" + "|".join(row) + "|"
            )
        ]

        if not cleaned_rows:
            return None

        # Determine maximum number of columns
        max_columns = max(
            len(row)
            for row in cleaned_rows
        )

        # Make every row have the same number of columns
        for row in cleaned_rows:
            while len(row) < max_columns:
                row.append("")

        formatted_rows = []

        for row_index, row in enumerate(cleaned_rows):

            formatted_row = []

            for cell in row:
                cell_text = format_inline(cell)

                if row_index == 0:
                    formatted_row.append(
                        Paragraph(
                            cell_text,
                            table_header_style
                        )
                    )
                else:
                    formatted_row.append(
                        Paragraph(
                            cell_text,
                            table_style
                        )
                    )

            formatted_rows.append(formatted_row)

        # Calculate usable page width
        usable_width = (
            A4[0]
            - document.leftMargin
            - document.rightMargin
        )

        column_width = usable_width / max_columns

        column_widths = [
            column_width
            for _ in range(max_columns)
        ]

        table = Table(
            formatted_rows,
            colWidths=column_widths,
            repeatRows=1,
            hAlign="LEFT",
        )

        table.setStyle(
            TableStyle([
                # Grid
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey,
                ),

                # Header
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#E8E8E8"),
                ),

                # Header alignment
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),

                # Padding
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ])
        )

        return table

    # =========================================================
    # 6. Build document elements
    # =========================================================

    elements = []

    # ---------------------------------------------------------
    # PDF title
    # ---------------------------------------------------------
    title = f"{project.project_name} document"
    
    elements.append(
        Paragraph(
           title,
            title_style,
        )
    )

    elements.append(
        Paragraph(
            "Generated Code Documentation",
            heading1_style,
        )
    )

    elements.append(Spacer(1, 5))

    # ---------------------------------------------------------
    # File information
    # ---------------------------------------------------------
    if file_info_flag:
        elements.append(
            Paragraph(
                f"<b>File:</b> {escape(str(source.file_name))}",
                normal_style,
            )
        )

        elements.append(
            Paragraph(
                f"<b>Language:</b> {escape(str(source.language))}",
                normal_style,
            )
        )

    
        elements.append(Spacer(1, 12))

    # =========================================================
    # 7. Parse Markdown
    # =========================================================

    lines = doc.content.splitlines()

    table_data = []

    def flush_table():
        nonlocal table_data

        if table_data:
            table = create_table(table_data)

            if table is not None:
                elements.append(
                    KeepTogether([
                        table,
                        Spacer(1, 10),
                    ])
                )

        table_data = []

    for raw_line in lines:

        line = raw_line.strip()

        # -----------------------------------------------------
        # Empty line
        # -----------------------------------------------------

        if not line:
            if table_data:
                flush_table()

            elements.append(Spacer(1, 4))
            continue

        # -----------------------------------------------------
        # Markdown table
        # -----------------------------------------------------

        if line.startswith("|"):

            cells = [
                cell.strip()
                for cell in line.strip("|").split("|")
            ]

            table_data.append(cells)
            continue

        # If previous table ended
        if table_data:
            flush_table()

        # -----------------------------------------------------
        # Horizontal rule
        # -----------------------------------------------------

        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", line):

            elements.append(
                Spacer(1, 4)
            )

            elements.append(
                Table(
                    [[""]],
                    colWidths=[
                        A4[0]
                        - document.leftMargin
                        - document.rightMargin
                    ],
                    rowHeights=[0.5],
                    style=TableStyle([
                        (
                            "LINEBELOW",
                            (0, 0),
                            (-1, -1),
                            0.5,
                            colors.grey,
                        )
                    ]),
                )
            )

            elements.append(
                Spacer(1, 8)
            )

            continue

        # -----------------------------------------------------
        # H1
        # # Heading
        # -----------------------------------------------------

        if re.match(r"^#\s+", line):

            text = re.sub(
                r"^#\s+",
                "",
                line,
            )

            elements.append(
                Paragraph(
                    format_inline(text),
                    heading1_style,
                )
            )

            continue

        # -----------------------------------------------------
        # H2
        # ## Heading
        # -----------------------------------------------------

        if re.match(r"^##\s+", line):

            text = re.sub(
                r"^##\s+",
                "",
                line,
            )

            elements.append(
                Paragraph(
                    format_inline(text),
                    heading2_style,
                )
            )

            continue

        # -----------------------------------------------------
        # H3
        # ### Heading
        # -----------------------------------------------------

        if re.match(r"^###\s+", line):

            text = re.sub(
                r"^###\s+",
                "",
                line,
            )

            elements.append(
                Paragraph(
                    format_inline(text),
                    heading3_style,
                )
            )

            continue

        # -----------------------------------------------------
        # Bullet list
        # -----------------------------------------------------

        if re.match(r"^[-*+]\s+", line):

            text = re.sub(
                r"^[-*+]\s+",
                "",
                line,
            )

            elements.append(
                Paragraph(
                    "• " + format_inline(text),
                    bullet_style,
                )
            )

            continue

        # -----------------------------------------------------
        # Numbered list
        # -----------------------------------------------------

        numbered_match = re.match(
            r"^(\d+)\.\s+(.*)",
            line,
        )

        if numbered_match:

            number = numbered_match.group(1)
            text = numbered_match.group(2)

            elements.append(
                Paragraph(
                    f"{number}. {format_inline(text)}",
                    numbered_style,
                )
            )

            continue

        # -----------------------------------------------------
        # Normal paragraph
        # -----------------------------------------------------

        elements.append(
            Paragraph(
                format_inline(line),
                normal_style,
            )
        )

    # =========================================================
    # 8. Flush final table
    # =========================================================

    if table_data:
        flush_table()

    # =========================================================
    # 9. Build PDF
    # =========================================================

    document.build(elements)

    pdf_file.seek(0)

    # =========================================================
    # 10. Return PDF response
    # =========================================================

    return StreamingResponse(
        pdf_file,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; '
                f'filename="{file_name}_documentation.pdf"'
            )
        },
    )