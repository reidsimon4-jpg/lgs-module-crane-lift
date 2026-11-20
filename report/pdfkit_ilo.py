"""Small PDF builder in the Infinity Living look (navy / sky, Segoe UI), with a cover page.
Used by make_dossier.py and make_proposal.py for the SHAPE Modular WA pack."""
import os, io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, Image,
                                PageBreak, KeepTogether, NextPageTemplate, CondPageBreak)
from PIL import Image as PILImage

F = r"C:\Windows\Fonts"
for name, file in (("Seg", "segoeui.ttf"), ("SegB", "segoeuib.ttf"), ("SegSB", "seguisb.ttf"), ("SegL", "segoeuil.ttf"), ("SegI", "segoeuii.ttf")):
    pdfmetrics.registerFont(TTFont(name, os.path.join(F, file)))
addMapping("Seg", 0, 0, "Seg"); addMapping("Seg", 1, 0, "SegB"); addMapping("Seg", 0, 1, "SegI"); addMapping("Seg", 1, 1, "SegB")

NAVY, SKY, SKY2, INK, MUTED, LINE, PAPER, WARN, OK, BAD = (HexColor(c) for c in
    ("#0f172a", "#0ea5e9", "#38bdf8", "#1c2430", "#64748b", "#d9dfe7", "#f3f5f8", "#b45309", "#15803d", "#b91c1c"))
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ilo-logo.png")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Doc:
    def __init__(self, path, title, subtitle, size="A4", banner="", footer="Infinity Living Options", date=""):
        self.path, self.title, self.subtitle, self.banner, self.footer, self.date = path, title, subtitle, banner, footer, date
        self.page = {"A4": A4, "A4L": landscape(A4)}[size]
        self.W, self.H = self.page
        self.m = 16 * mm if size == "A4" else 15 * mm
        self.story = []
        self.cover_info = None
        base = 9.4 if size == "A4" else 9.6
        self.st = {
            "h1": ParagraphStyle("h1", fontName="SegB", fontSize=17, leading=21, textColor=NAVY, spaceBefore=2, spaceAfter=6),
            "h2": ParagraphStyle("h2", fontName="SegB", fontSize=11.5, leading=14.5, textColor=NAVY, spaceBefore=9, spaceAfter=3),
            "kicker": ParagraphStyle("kicker", fontName="SegSB", fontSize=8, leading=10, textColor=SKY, spaceAfter=1),
            "p": ParagraphStyle("p", fontName="Seg", fontSize=base, leading=base * 1.42, textColor=INK, spaceAfter=4.5, alignment=TA_LEFT),
            "lead": ParagraphStyle("lead", fontName="SegL", fontSize=12, leading=16.5, textColor=INK, spaceAfter=6),
            "small": ParagraphStyle("small", fontName="Seg", fontSize=7.6, leading=10, textColor=MUTED, spaceAfter=3),
            "cap": ParagraphStyle("cap", fontName="Seg", fontSize=7.6, leading=9.8, textColor=MUTED, spaceBefore=2, spaceAfter=2),
            "cell": ParagraphStyle("cell", fontName="Seg", fontSize=7.9, leading=10.2, textColor=INK),
            "cellb": ParagraphStyle("cellb", fontName="SegSB", fontSize=7.9, leading=10.2, textColor=INK),
            "head": ParagraphStyle("head", fontName="SegSB", fontSize=7.9, leading=10.2, textColor=white),
            "li": ParagraphStyle("li", fontName="Seg", fontSize=base, leading=base * 1.42, textColor=INK, leftIndent=11, bulletIndent=1, spaceAfter=2.2),
            "statb": ParagraphStyle("statb", fontName="SegB", fontSize=19, leading=21, textColor=NAVY),
            "stats": ParagraphStyle("stats", fontName="Seg", fontSize=7.8, leading=10, textColor=MUTED),
        }

    @property
    def aw(self):
        return self.W - 2 * self.m

    # ---------- content ----------
    def cover(self, kicker, title, subtitle, prepared, image=None, chips=()):
        self.cover_info = dict(kicker=kicker, title=title, subtitle=subtitle, prepared=prepared, image=image, chips=chips)
        self.story += [NextPageTemplate("body"), PageBreak()]

    def h1(self, t, kicker=None):
        if kicker:
            self.story.append(CondPageBreak(60 * mm))
            self.story.append(Paragraph(esc(kicker).upper(), self.st["kicker"]))
        self.story.append(Paragraph(t, self.st["h1"]))

    def h2(self, t):
        self.story.append(CondPageBreak(28 * mm))
        self.story.append(Paragraph(t, self.st["h2"]))

    def p(self, t, style="p"):
        self.story.append(Paragraph(t, self.st[style]))

    def lead(self, t):
        self.p(t, "lead")

    def small(self, t):
        self.p(t, "small")

    def gap(self, h=4):
        self.story.append(Spacer(1, h * mm))

    def br(self):
        self.story.append(PageBreak())

    def bullets(self, items, style="li"):
        for it in items:
            self.story.append(Paragraph(it, self.st[style], bulletText="\u2022"))

    def callout(self, title, text, kind="info"):
        col = {"info": SKY, "warn": WARN, "ok": OK, "bad": BAD}[kind]
        body = "<font name='SegB'>%s</font>%s" % (title, ("<br/>" + text) if text else "")
        t = Table([[Paragraph(body, self.st["p"])]], colWidths=[self.aw])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PAPER), ("LINEBEFORE", (0, 0), (0, -1), 3, col),
                               ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                               ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        self.story += [t, Spacer(1, 3 * mm)]

    def stats(self, items, cols=4):
        cells = [[Paragraph(esc(b), self.st["statb"]), Paragraph(s, self.st["stats"])] for b, s in items]
        rows, row = [], []
        for c in cells:
            row.append(c)
            if len(row) == cols:
                rows.append(row); row = []
        if row:
            rows.append(row + [""] * (cols - len(row)))
        w = self.aw / cols
        t = Table([[self._stack(c) if c else "" for c in r] for r in rows], colWidths=[w] * cols)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
        self.story += [t, Spacer(1, 3 * mm)]

    def _stack(self, c):
        t = Table([[c[0]], [c[1]]], colWidths=[self.aw / 4 - 8])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PAPER), ("LINEABOVE", (0, 0), (-1, 0), 2, SKY),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, 0), 7), ("BOTTOMPADDING", (0, -1), (-1, -1), 7)]))
        return t

    def table(self, header, rows, widths=None, bold_first=False, zebra=True, font_cell="cell"):
        n = len(header)
        if widths is None:
            widths = [1] * n
        tot = float(sum(widths)); widths = [self.aw * w / tot for w in widths]
        def cell(c, i):
            st = "cellb" if (bold_first and i == 0) else font_cell
            return Paragraph(c if isinstance(c, str) and ("<" in c and ">" in c) else esc("" if c is None else c), self.st[st])
        data = [[Paragraph(esc(h), self.st["head"]) for h in header]] + [[cell(c, i) for i, c in enumerate(r)] for r in rows]
        t = Table(data, colWidths=widths, repeatRows=1)
        ts = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
              ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        if zebra:
            ts.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f8fafc")]))
        t.setStyle(TableStyle(ts)); self.story += [t, Spacer(1, 3.5 * mm)]

    def _img(self, path, w, h_max=None):
        im = PILImage.open(path); iw, ih = im.size
        k = w / iw
        if h_max and ih * k > h_max:
            k = h_max / ih
        if iw * ih > 4_000_000:
            s = (4_000_000 / (iw * ih)) ** 0.5
            im = im.convert("RGB").resize((int(iw * s), int(ih * s)), PILImage.LANCZOS)
            b = io.BytesIO(); im.save(b, "JPEG", quality=86); b.seek(0); src = b
        else:
            src = path
        return Image(src, width=iw * k, height=ih * k)

    def image(self, path, caption=None, w_frac=1.0, h_max_mm=None):
        el = [self._img(path, self.aw * w_frac, h_max_mm * mm if h_max_mm else None)]
        if caption:
            el.append(Paragraph(caption, self.st["cap"]))
        self.story.append(KeepTogether(el)); self.story.append(Spacer(1, 3 * mm))

    def grid(self, items, cols=2, h_max_mm=None, gap_mm=5):
        """items: [(path, caption)]"""
        w = (self.aw - gap_mm * mm * (cols - 1)) / cols
        rows, row = [], []
        for path, cap in items:
            row.append([self._img(path, w, h_max_mm * mm if h_max_mm else None), Paragraph(cap, self.st["cap"])])
            if len(row) == cols:
                rows.append(row); row = []
        if row:
            rows.append(row + [""] * (cols - len(row)))
        widths = []
        for i in range(cols):
            widths.append(w)
            if i < cols - 1:
                widths.append(gap_mm * mm)
        data = []
        for r in rows:
            line = []
            for i, c in enumerate(r):
                line.append(c)
                if i < cols - 1:
                    line.append("")
            data.append(line)
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        self.story += [t, Spacer(1, 2 * mm)]

    def two_col(self, left_flowables, right_flowables, split=0.5, gap_mm=7):
        lw = self.aw * split - gap_mm * mm / 2; rw = self.aw - lw - gap_mm * mm
        t = Table([[left_flowables, "", right_flowables]], colWidths=[lw, gap_mm * mm, rw])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        self.story += [t, Spacer(1, 2 * mm)]

    def para(self, t, style="p"):
        return Paragraph(t, self.st[style])

    def bl(self, items, style="li"):
        return [Paragraph(i, self.st[style], bulletText="\u2022") for i in items]

    # ---------- page furniture ----------
    def _cover_page(self, c, doc):
        ci = self.cover_info; W, H = self.W, self.H
        land = W > H
        c.saveState()
        c.setFillColor(NAVY); c.rect(0, 0, W, H, 0, 1)
        if land:
            c.setFillColor(HexColor("#13213b")); c.rect(W * 0.5, 0, W * 0.5, H, 0, 1)
        else:
            c.setFillColor(HexColor("#13213b")); c.rect(0, 0, W, H * 0.47, 0, 1)
        x = self.m
        c.setFillColor(white); c.roundRect(x, H - 31 * mm, 38 * mm, 19 * mm, 3, 0, 1)
        c.drawImage(LOGO, x + 3 * mm, H - 29 * mm, width=32 * mm, height=15 * mm, preserveAspectRatio=True, mask="auto")
        y = H - 52 * mm
        c.setFillColor(SKY2); c.setFont("SegSB", 10); c.drawString(x, y, ci["kicker"].upper())
        c.setFillColor(white); size = 30 if self.W < 700 else 32
        c.setFont("SegB", size)
        y -= 13 * mm
        for line in ci["title"].split("\n"):
            c.drawString(x, y, line); y -= size * 1.18
        c.setFillColor(HexColor("#cbd5e1")); c.setFont("SegL", 13)
        y -= 2 * mm
        from reportlab.lib.utils import simpleSplit
        for para in ci["subtitle"].split("\n"):                      # wrap to the page width
            for line in simpleSplit(para, "SegL", 13, W - 2 * self.m) or [""]:
                c.drawString(x, y, line); y -= 17
        y -= 4 * mm
        cx = x
        for chip, col in ci["chips"]:
            tw = pdfmetrics.stringWidth(chip.upper(), "SegSB", 7.5) + 14
            if cx > x and cx + tw > W - self.m:                           # next row when the chip would run off the page
                cx = x; y -= 19
            c.setStrokeColor(HexColor(col)); c.setFillColor(HexColor(col)); c.setLineWidth(0.8)
            c.roundRect(cx, y - 4, tw, 14, 7, 1, 0)
            c.setFont("SegSB", 7.5); c.drawString(cx + 7, y + 0.5, chip.upper()); cx += tw + 6
        if ci.get("image") and os.path.exists(ci["image"]):
            im = PILImage.open(ci["image"]); iw, ih = im.size
            if land:
                boxw, boxh = W * 0.5 - 2 * self.m, H - 60 * mm
                k = min(boxw / iw, boxh / ih); dw, dh = iw * k, ih * k
                bx = W * 0.5 + self.m + (boxw - dw) / 2; by = 24 * mm + (boxh - dh) / 2
            else:
                boxw, boxh = W - 2 * self.m, H * 0.40
                k = min(boxw / iw, boxh / ih); dw, dh = iw * k, ih * k
                bx = (W - dw) / 2; by = 24 * mm
            c.setFillColor(white); c.roundRect(bx - 4 * mm, by - 4 * mm, dw + 8 * mm, dh + 8 * mm, 6, 0, 1)
            c.drawImage(ci["image"], bx, by, width=dw, height=dh, preserveAspectRatio=True, mask="auto")
        c.setFillColor(HexColor("#94a3b8")); c.setFont("Seg", 8.5)
        c.drawString(self.m, 11 * mm, ci["prepared"])
        c.drawRightString(W - self.m, 11 * mm, self.date)
        c.restoreState()

    def _body_page(self, c, doc):
        c.saveState(); W, H = self.W, self.H
        c.setFillColor(NAVY); c.rect(0, H - 14 * mm, W, 14 * mm, 0, 1)
        x = self.m
        c.setFillColor(white); c.roundRect(x - 1.5, H - 12 * mm, 19 * mm, 10 * mm, 2, 0, 1)
        c.drawImage(LOGO, x, H - 11.4 * mm, width=16 * mm, height=8.8 * mm, preserveAspectRatio=True, mask="auto")
        x += 24 * mm
        c.setFillColor(white); c.setFont("SegB", 10.5); c.drawString(x, H - 7.2 * mm, self.title)
        c.setFont("Seg", 7.5); c.setFillColor(HexColor("#cbd5e1")); c.drawString(x, H - 11 * mm, self.subtitle)
        if self.banner:
            c.setFillColor(HexColor("#fbbf24")); c.setFont("SegSB", 7); c.drawRightString(W - self.m, H - 7.2 * mm, self.banner)
        c.setFillColor(HexColor("#cbd5e1")); c.setFont("Seg", 7.5); c.drawRightString(W - self.m, H - 11 * mm, self.date)
        c.setFillColor(MUTED); c.setFont("Seg", 7); c.drawString(self.m, 7 * mm, self.footer)
        c.drawRightString(W - self.m, 7 * mm, "page %d" % doc.page)
        c.restoreState()

    def build(self):
        d = BaseDocTemplate(self.path, pagesize=self.page, leftMargin=self.m, rightMargin=self.m, topMargin=20 * mm, bottomMargin=13 * mm,
                            title=self.title, author="Infinity Living Options", subject=self.subtitle)
        body = Frame(self.m, 13 * mm, self.W - 2 * self.m, self.H - 33 * mm, id="b", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        cover = Frame(self.m, 13 * mm, self.W - 2 * self.m, self.H - 33 * mm, id="c")
        tpls = []
        if self.cover_info:
            tpls.append(PageTemplate(id="cover", frames=[cover], onPage=self._cover_page))
        tpls.append(PageTemplate(id="body", frames=[body], onPage=self._body_page))
        d.addPageTemplates(tpls)
        if self.cover_info:
            self.story.insert(0, Spacer(1, 1))
        d.build(self.story)
        return self.path
