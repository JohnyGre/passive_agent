"""
FILE AGENT - PRO VERSION
Zlúčená stabilita: JSON Rescue (Hrubá sila) + ReportLab (Pokročilý Styling).
"""

import json
import logging
import re
import os
from datetime import datetime
from pathlib import Path

from config import PRODUCTS_DIR

log = logging.getLogger("FileAgent")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, PageBreak
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    log.warning("⚠️ ReportLab nie je nainštalovaný.")

class FileAgent:
    def save(self, product: dict) -> dict[str, Path]:
        # --- 1. JSON RESCUE (Hrubá sila) ---
        if "raw_content" in product and isinstance(product["raw_content"], str):
            try:
                raw_text = product["raw_content"]
                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1
                if start >= 0 and end > start:
                    clean_json = raw_text[start:end]
                    # strict=False zachráni useknuté stringy a špeciálne znaky
                    extracted = json.loads(clean_json, strict=False)
                    if isinstance(extracted, dict):
                        product.update(extracted)
                        product.pop("raw_content", None)
                        log.info("✅ JSON úspešne zachránený a deserializovaný!")
            except Exception as e:
                log.warning(f"⚠️ Záchrana JSONu zlyhala: {e}")

        title = product.get("title", "Digital Product")
        safe = self._safe_filename(title)
        
        root_folder = PRODUCTS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe}"
        root_folder.mkdir(parents=True, exist_ok=True)

        diy_folder = root_folder / "v1_DIY_Basic"
        diy_folder.mkdir(exist_ok=True)
        
        pro_folder = root_folder / "v2_PRO_Automation_Kit"
        pro_folder.mkdir(exist_ok=True)

        # Uložíme čisté dáta
        (root_folder / "data.json").write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")

        pdf_name = f"{safe}_Guide.pdf"
        if REPORTLAB_AVAILABLE:
            try:
                self._generate_reportlab_pdf(product, diy_folder / pdf_name)
                self._generate_reportlab_pdf(product, pro_folder / pdf_name)
                log.info(f"✅ PDF profesionálne vygenerované: {pdf_name}")
            except Exception as e:
                log.error(f"❌ PDF styling zlyhal: {e}")

        # PRO EXTRA SÚBORY
        python_code = product.get("python_script") or product.get("python_helper")
        if python_code:
            (pro_folder / "automation_script.py").write_text(str(python_code), encoding="utf-8")
            (pro_folder / "requirements.txt").write_text("pandas\nrequests\nhttpx\nsqlite3\n", encoding="utf-8")

        return {"json": root_folder / "data.json"}

    def _smart_clean(self, text):
        if not text: return ""
        return str(text).encode("ascii", "ignore").decode("ascii").strip()

    def _generate_reportlab_pdf(self, product, output_path):
        doc = SimpleDocTemplate(str(output_path), pagesize=A4)
        styles = getSampleStyleSheet()
        
        # Štýly
        title_style = ParagraphStyle('T', parent=styles['Heading1'], fontSize=20, alignment=TA_CENTER, spaceAfter=20, textColor=colors.HexColor('#2c3e50'))
        h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=14, spaceBefore=12, spaceAfter=8, textColor=colors.HexColor('#2c3e50'))
        body_style = ParagraphStyle('B', parent=styles['Normal'], fontSize=10, leading=14)
        code_style = ParagraphStyle('C', parent=body_style, fontName='Courier', fontSize=8, textColor=colors.darkblue, backColor=colors.whitesmoke, borderPadding=10)

        elements = [Paragraph(self._smart_clean(product.get("title", "Digital Guide")), title_style)]
        
        if product.get("description"):
            elements.append(Paragraph(self._smart_clean(product.get("description", "")), body_style))
            elements.append(Spacer(1, 20))

        # A. Mini Guides (Sections)
        sections = product.get("sections", [])
        for s in sections:
            elements.append(Paragraph(f"<b>{self._smart_clean(s.get('heading', ''))}</b>", h2_style))
            elements.append(Paragraph(self._smart_clean(s.get("content", "")), body_style))
            elements.append(Spacer(1, 10))

        # B. Prompt Packs (Prompts)
        prompts = product.get("prompts", [])
        if prompts:
            elements.append(Paragraph("STRATEGIC PROMPT LIBRARY", h2_style))
            for p in prompts:
                name = p.get("name") or "Prompt"
                elements.append(Paragraph(f"<b>{self._smart_clean(name)}</b>", body_style))
                elements.append(Paragraph(self._smart_clean(p.get("prompt", "")), ParagraphStyle('P', parent=body_style, leftIndent=15, textColor=colors.darkslategray)))
                elements.append(Spacer(1, 10))

        # C. Code Block (Automation Script)
        python_script = product.get("python_script") or product.get("python_helper")
        if python_script:
            elements.append(PageBreak())
            elements.append(Paragraph("<b>Automation Script (Plug & Play)</b>", h2_style))
            # XML Escape pre ochranu ReportLabu
            safe_code = str(python_script).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            elements.append(Preformatted(safe_code, code_style))

        # Fallback
        if not sections and not prompts and not python_script:
            elements.append(Paragraph("PRODUCT DETAILS (RAW)", h2_style))
            raw = product.get("raw_content", str(product))
            for line in str(raw).split("\n"):
                if len(line.strip()) > 5:
                    elements.append(Paragraph(self._smart_clean(line), body_style))

        # Footer s číslovaním strán
        def _add_footer(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 9)
            canvas.drawCentredString(A4[0]/2, 20, f"Page {doc.page} | Premium Automation Kit")
            canvas.restoreState()

        doc.build(elements, onFirstPage=_add_footer, onLaterPages=_add_footer)

    @staticmethod
    def _safe_filename(text: str, max_len: int = 40) -> str:
        safe = re.sub(r'[^\w\s-]', '', text.lower())
        safe = re.sub(r'[\s-]+', '_', safe)
        return safe[:max_len].strip("_")
