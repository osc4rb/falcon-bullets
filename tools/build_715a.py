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


def is_bar(d):
    """A letter part drawn as an upright rectangle: I and l stems (regular and bold), hyphens, small marks.

    Italic I and l are slanted parallelograms; viewers already anti-alias those, so they are left alone.
    """
    r = d["rect"]
    if not (d.get("fill") is not None and d.get("color") is None and len(d["items"]) <= 5
            and r.width < 3 and r.height < 9):
        return False
    for it in d["items"]:
        if it[0] == "re":
            continue
        if it[0] != "l":
            return False
        p, q = it[1], it[2]
        if abs(p.x - q.x) > 0.01 and abs(p.y - q.y) > 0.01:   # a slanted edge: not a rectangle
            return False
    return True


def is_stem(r):
    """A regular-weight I or l stem (bold stems are wider and keep their exact width)."""
    return r.width < 1.3 and 3.5 < r.height < 9


def soften_bars(doc):
    """Redraw rectangle-shaped letters so viewers render them like every other letter.

    The flattened copy draws I and l as plain rectangles. Browsers (pdfium) snap plain rectangle
    fills to whole pixels with hard edges, so those letters look bold next to the anti-aliased
    curved letters. The copy was also made by printing at 600 dpi, which rounded every edge to a
    0.12pt grid, leaving the same stem 0.84 or 0.96pt wide. Each bar is removed and redrawn with
    the same outline (one edge as a straight-line curve, so it is no longer a "rectangle") at the
    average width for its letter height, centered where it was.
    """
    bars = [[(d["rect"], d["fill"]) for d in page.get_drawings() if is_bar(d)] for page in doc]
    by_height = {}
    for page_bars in bars:
        for r, _ in page_bars:
            if is_stem(r):
                by_height.setdefault(round(r.height, 1), []).append(r.width)
    width = {h: sum(ws) / len(ws) for h, ws in by_height.items()}
    for page, page_bars in zip(doc, bars):
        for r, _ in page_bars:
            page.add_redact_annot(r + (-0.02, -0.02, 0.02, 0.02), fill=False)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                              graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                              text=pymupdf.PDF_REDACT_TEXT_NONE)
        shape = page.new_shape()
        for r, fill in page_bars:
            w = width[round(r.height, 1)] if is_stem(r) else r.width
            cx = (r.x0 + r.x1) / 2
            x0, x1, y0, y1 = cx - w / 2, cx + w / 2, r.y0, r.y1
            third = (y1 - y0) / 3
            shape.draw_line((x0, y0), (x1, y0))
            shape.draw_bezier((x1, y0), (x1, y0 + third), (x1, y1 - third), (x1, y1))
            shape.draw_line((x1, y1), (x0, y1))
            shape.draw_line((x0, y1), (x0, y0))
            shape.finish(fill=fill, color=None, width=0, closePath=True)
        shape.commit()
    print("redrew rectangle marks:", sum(len(b) for b in bars), "| regular stem widths by height:",
          {h: round(w, 3) for h, w in sorted(width.items())})


SEGMENT = re.compile(rb"([-\d.]+)\s+([-\d.]+)\s+m\s+([-\d.]+)\s+([-\d.]+)\s+l\s+S")
FIRST_CM = re.compile(rb"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+cm")


def remove_check_marks(doc):
    """Delete old check marks: an X is two stroked diagonals inside a checkbox.

    Redaction doesn't remove these strokes, so they are deleted from the content stream directly,
    and only when both ends of the stroke lie inside a checkbox square.
    """
    removed = 0
    for pno, page in enumerate(doc):
        boxes = [pymupdf.Rect(x, y, x + 10, y + 10)
                 for (rp, y, xs, _, _) in CHECK_ROWS if rp == pno for x in xs]
        page.clean_contents()
        xref = page.get_contents()[0]
        raw = doc.xref_stream(xref)
        a, _, _, d, e, f = (float(v) for v in FIRST_CM.search(raw).groups())  # the copy's base transform
        height = page.rect.height

        def drop(m):
            nonlocal removed
            x1, y1, x2, y2 = (float(v) for v in m.groups())
            p1 = pymupdf.Point(a * x1 + e, height - (d * y1 + f))
            p2 = pymupdf.Point(a * x2 + e, height - (d * y2 + f))
            if any(p1 in b and p2 in b for b in boxes):
                removed += 1
                return b""
            return m.group(0)

        doc.update_stream(xref, SEGMENT.sub(drop, raw))
    print("removed old check-mark strokes:", removed)


def main(flat_pdf, official_pdf, out_pdf):
    tpl = load_template(official_pdf)
    form1 = tpl.find(NS + "subform")
    pages = [s for s in form1 if s.tag == NS + "subform"]
    specs = [list(zip(P1_NAMES, page_fields(pages[0]))),
             list(zip(P2_NAMES, page_fields(pages[1])))]

    doc = pymupdf.open(flat_pdf)
    remove_check_marks(doc)

    # 1) Remove any old entries: delete the line art inside each entry area and checkbox.
    #    fill=False paints nothing, so the boxes' recessed (shaded) edges stay exactly as drawn.
    for pno, page in enumerate(doc):
        for name, (kind, multi, r) in specs[pno]:
            page.add_redact_annot(r + (1.2, 1.2, -1.2, -1.2), fill=False)
        for (rp, y, xs, _, _) in CHECK_ROWS:
            if rp == pno:
                for x in xs:
                    page.add_redact_annot(pymupdf.Rect(x + 0.1, y + 0.1, x + 9.9, y + 9.9), fill=False)  # covers the X, not the outline
        if pno == 1:
            for _, r in ROLES:
                page.add_redact_annot(r, fill=False)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                              graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                              text=pymupdf.PDF_REDACT_TEXT_REMOVE)

    soften_bars(doc)

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
