"""Build a fillable copy of USAFA Form 715A from the official artwork.

The official 715A is an encrypted, Adobe-only (XFA) form, so nothing outside
Acrobat can fill it. This script takes a flattened copy of the real form
(vector artwork), removes any old entries, and adds standard AcroForm fields
at the exact box positions read from the official XFA template.

Usage:  python build_715a.py <flattened_715a.pdf> <official_715a.pdf> <out.pdf>
"""
import re
import sys
import xml.etree.ElementTree as ET

import pymupdf
import pypdf

NS = "{http://www.xfa.org/schema/xfa-template/3.6/}"
ORIGIN = (18.0, 18.0)  # content area offset (0.25in)


def unit(v):
    if not v:
        return 0.0
    m = re.match(r"([-\d.]+)(mm|in|pt|cm)?", v)
    return float(m.group(1)) * {"mm": 72 / 25.4, "in": 72, "pt": 1, "cm": 72 / 2.54}[m.group(2) or "in"]


def load_template(official_pdf):
    r = pypdf.PdfReader(official_pdf)
    xfa = r.trailer["/Root"]["/AcroForm"]["/XFA"].get_object()
    for i in range(0, len(xfa), 2):
        if str(xfa[i]) == "template":
            t = xfa[i + 1].get_object().get_data().decode("utf-8", "ignore")
            return ET.fromstring(re.sub(r"<\?.*?\?>", "", t))
    raise SystemExit("no XFA template found")


def ui_rect(field, x, y):
    """Entry (input) rectangle of an XFA field, in page points."""
    w, h = unit(field.get("w")), unit(field.get("h"))
    m = field.find(NS + "margin")
    mt = unit(m.get("topInset")) if m is not None else 0
    mb = unit(m.get("bottomInset")) if m is not None else 0
    ml = unit(m.get("leftInset")) if m is not None else 0
    mr = unit(m.get("rightInset")) if m is not None else 0
    x0, y0, x1, y1 = x + ml, y + mt, x + w - mr, y + h - mb
    cap = field.find(NS + "caption")
    if cap is not None:
        res, place = unit(cap.get("reserve")), cap.get("placement", "left")
        if place == "top":
            y0 += res
        elif place == "left":
            x0 += res
        elif place == "right":
            x1 -= res
        elif place == "bottom":
            y1 -= res
    return pymupdf.Rect(x0, y0, x1, y1)


def page_fields(content_subform):
    """Non-table fields of one page, in document order: (kind, rect)."""
    out = []
    ox, oy = ORIGIN
    for f in content_subform:
        if f.tag != NS + "field":
            continue
        ui = f.find(NS + "ui")
        kind = ui[0].tag.replace(NS, "") if ui is not None and len(ui) else "textEdit"
        multi = kind == "textEdit" and ui[0].get("multiLine") == "1"
        rect = ui_rect(f, ox + unit(f.get("x")), oy + unit(f.get("y")))
        out.append((kind, multi, rect))
    return out


# Field names, in template document order (tables handled separately).
P1_NAMES = ["name", "class_rank", "unit", "semester", "duty_title", "duty_desc",
            "s1", "s2", "s3", "s4",
            "rater_sig", "rater_name", "rater_duty_title", "rater_date"]
P2_NAMES = ["cc_sig", "cc_date", "cc_duty_title", "cc_name", "amt_review",
            "pp_comments", "pp_avg",
            "pp_sig", "pp_date", "pp_duty_title", "pp_name",
            "ratee_sig", "ratee_date"]
# Checkbox rows: (page, top y, x positions, field prefix, labels)
RATING = ["needs_improvement", "developing", "proficient", "highly_proficient", "exceptionally_skilled"]
LEVEL = ["top10", "top25", "average", "below_average", "does_not_meet"]
X1 = [22.8, 138.0, 253.2, 368.4, 483.6]
X2 = [22.8, 138.0, 253.2, 369.0, 471.4]
CHECK_ROWS = [(0, 337.0, X1, "s1", RATING), (0, 427.0, X1, "s2", RATING),
              (0, 517.0, X1, "s3", RATING), (0, 607.0, X1, "s4", RATING),
              (1, 58.0, X2, "cc_level", LEVEL), (1, 256.0, X2, "pp_level", LEVEL)]
ROLES = [("role_a", pymupdf.Rect(32, 389, 206, 403)),
         ("role_b", pymupdf.Rect(224, 389, 398, 403)),
         ("role_c", pymupdf.Rect(416, 389, 590, 403))]

DO_NOT_SCROLL = 1 << 23


def add_text(page, name, rect, multi=False, size=9):
    w = pymupdf.Widget()
    w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    w.field_name = name
    w.rect = rect
    w.text_font = "Helv"
    w.text_fontsize = size
    w.field_value = ""
    w.border_width = 0
    w.fill_color = None
    if multi:
        w.field_flags = pymupdf.PDF_TX_FIELD_IS_MULTILINE | DO_NOT_SCROLL
    page.add_widget(w)


def add_check(page, name, rect):
    w = pymupdf.Widget()
    w.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    w.field_name = name
    w.rect = rect
    w.border_width = 0
    w.fill_color = None
    w.button_caption = "8"  # ZapfDingbats cross, matching the official X mark
    w.field_value = False
    page.add_widget(w)


def add_sig(page, name, rect):
    w = pymupdf.Widget()
    w.field_type = pymupdf.PDF_WIDGET_TYPE_SIGNATURE
    w.field_name = name
    w.rect = rect
    w.border_width = 0
    w.fill_color = None
    page.add_widget(w)


def add_combo(page, name, rect, choices):
    w = pymupdf.Widget()
    w.field_type = pymupdf.PDF_WIDGET_TYPE_COMBOBOX
    w.field_name = name
    w.rect = rect
    w.choice_values = choices
    w.field_value = ""
    w.text_font = "Helv"
    w.text_fontsize = 9
    w.border_width = 0
    w.fill_color = None
    page.add_widget(w)


def main(flat_pdf, official_pdf, out_pdf):
    tpl = load_template(official_pdf)
    form1 = tpl.find(NS + "subform")
    pages = [s for s in form1 if s.tag == NS + "subform"]
    specs = [list(zip(P1_NAMES, page_fields(pages[0]))),
             list(zip(P2_NAMES, page_fields(pages[1])))]

    doc = pymupdf.open(flat_pdf)

    # 1) Remove any old entries: redact every entry area and checkbox interior.
    for pno, page in enumerate(doc):
        for name, (kind, multi, r) in specs[pno]:
            page.add_redact_annot(r + (1.2, 1.2, -1.2, -1.2), fill=(1, 1, 1))
        for (rp, y, xs, _, _) in CHECK_ROWS:
            if rp == pno:
                for x in xs:
                    page.add_redact_annot(pymupdf.Rect(x + 0.9, y + 0.9, x + 9.1, y + 9.1), fill=(1, 1, 1))
        if pno == 1:
            for _, r in ROLES:
                page.add_redact_annot(r, fill=(1, 1, 1))
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                              graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                              text=pymupdf.PDF_REDACT_TEXT_REMOVE)

    # 2) Add fillable fields.
    for pno, page in enumerate(doc):
        for name, (kind, multi, r) in specs[pno]:
            r = r + (1.0, 0.8, -1.0, -0.8)
            if kind == "signature":
                add_sig(page, name, r)
            elif kind == "choiceList":
                add_combo(page, name, r, ["", "No", "Yes"])
            else:
                add_text(page, name, r, multi=multi)
        for (rp, y, xs, prefix, labels) in CHECK_ROWS:
            if rp == pno:
                for x, lab in zip(xs, labels):
                    add_check(page, f"{prefix}_{lab}", pymupdf.Rect(x, y, x + 10, y + 10))
        if pno == 1:
            for name, r in ROLES:
                add_text(page, name, r)

    doc.set_metadata({"title": "USAFA Form 715A (fillable copy)", "author": "", "subject": "",
                      "keywords": "", "creator": "Falcon Bullets", "producer": "Falcon Bullets"})
    doc.del_xml_metadata()
    doc.save(out_pdf, garbage=4, deflate=True, clean=True)
    print("wrote", out_pdf)


if __name__ == "__main__":
    main(*sys.argv[1:4])
