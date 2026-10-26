from __future__ import annotations

import html
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "presentation_output"
PPTX = OUT / "Patagonia_Content_Studio_Final.pptx"

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
for k, v in NS.items():
    ET.register_namespace(k if k not in {"r", "rel"} else "", v)

EMU = 914400
W, H = 960, 540
C = {
    "navy": "0B1220", "panel": "111C2E", "white": "F8FAFC", "muted": "A8B5C7",
    "teal": "5EEAD4", "blue": "60A5FA", "amber": "FBBF24", "coral": "FB7185",
    "green": "86EFAC", "line": "263650", "black": "081018",
}


def sx(v: float) -> int:
    return int(v / W * 13.333333 * EMU)


def sy(v: float) -> int:
    return int(v / H * 7.5 * EMU)


def E(tag: str, attrs: dict | None = None, parent=None):
    return ET.Element(tag, attrs or {}) if parent is None else ET.SubElement(parent, tag, attrs or {})


def fill(parent, color: str):
    sf = E("a:solidFill", parent=parent)
    E("a:srgbClr", {"val": C.get(color, color)}, sf)


def text_body(parent, text: str, size: int, color: str = "white", bold=False, align="l"):
    tb = E("p:txBody", parent=parent)
    E("a:bodyPr", {"wrap": "square", "anchor": "t", "lIns": "0", "rIns": "0", "tIns": "0", "bIns": "0"}, tb)
    E("a:lstStyle", parent=tb)
    for idx, raw in enumerate(text.split("\n")):
        p = E("a:p", parent=tb)
        if align != "l":
            E("a:pPr", {"algn": {"c": "ctr", "r": "r"}.get(align, "l")}, p)
        r = E("a:r", parent=p)
        rp = E("a:rPr", {"lang": "en-US", "sz": str(size * 100), "b": "1" if bold else "0"}, r)
        fill(rp, color)
        E("a:t", parent=r).text = raw
        if idx < len(text.split("\n")) - 1:
            E("a:endParaRPr", {"lang": "en-US"}, p)


def shape(tree, name, x0, y0, w0, h0, fill_color=None, line_color="line", text=None,
          size=12, color="white", bold=False, align="l", rounded=False):
    sp = E("p:sp", parent=tree)
    nv = E("p:nvSpPr", parent=sp)
    E("p:cNvPr", {"id": str(100 + len(list(tree))), "name": name}, nv)
    E("p:cNvSpPr", parent=nv); E("p:nvPr", parent=nv)
    sppr = E("p:spPr", parent=sp)
    xf = E("a:xfrm", parent=sppr)
    E("a:off", {"x": str(sx(x0)), "y": str(sy(y0))}, xf)
    E("a:ext", {"cx": str(sx(w0)), "cy": str(sy(h0))}, xf)
    geom = E("a:prstGeom", {"prst": "roundRect" if rounded else "rect"}, sppr)
    E("a:avLst", parent=geom)
    if fill_color:
        fill(sppr, fill_color)
    else:
        E("a:noFill", parent=sppr)
    ln = E("a:ln", {"w": "10000"}, sppr)
    if line_color == "none":
        E("a:noFill", parent=ln)
    else:
        fill(ln, line_color)
    if text is not None:
        text_body(sp, text, size, color, bold, align)
    return sp


def line(tree, x1, y1, x2, y2, color="teal", arrow=True):
    sp = E("p:sp", parent=tree)
    nv = E("p:nvSpPr", parent=sp); E("p:cNvPr", {"id": str(100 + len(list(tree))), "name": "connector"}, nv)
    E("p:cNvSpPr", parent=nv); E("p:nvPr", parent=nv)
    sppr = E("p:spPr", parent=sp)
    xf = E("a:xfrm", parent=sppr); E("a:off", {"x": str(sx(x1)), "y": str(sy(y1))}, xf); E("a:ext", {"cx": str(sx(x2-x1)), "cy": str(sy(y2-y1))}, xf)
    geom = E("a:prstGeom", {"prst": "line"}, sppr); E("a:avLst", parent=geom)
    ln = E("a:ln", {"w": "13000"}, sppr); fill(ln, color)
    if arrow:
        E("a:tailEnd", {"type": "triangle"}, ln)


def picture(tree, rel_id, x0, y0, w0, h0, name="evidence"):
    pic = E("p:pic", parent=tree)
    nv = E("p:nvPicPr", parent=pic); E("p:cNvPr", {"id": str(900 + len(list(tree))), "name": name}, nv); E("p:cNvPicPr", parent=nv); E("p:nvPr", parent=nv)
    blip = E("p:blipFill", parent=pic); E("a:blip", {"{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed": rel_id}, blip); E("a:stretch", parent=blip).append(E("a:fillRect"))
    sppr = E("p:spPr", parent=pic); xf = E("a:xfrm", parent=sppr); E("a:off", {"x": str(sx(x0)), "y": str(sy(y0))}, xf); E("a:ext", {"cx": str(sx(w0)), "cy": str(sy(h0))}, xf); geom = E("a:prstGeom", {"prst": "rect"}, sppr); E("a:avLst", parent=geom)


def slide_xml(content):
    sld = E("p:sld", {"showMasterSp": "0", "xmlns:a": NS["a"], "xmlns:p": NS["p"], "xmlns:r": NS["r"]})
    c = E("p:cSld", parent=sld); tree = E("p:spTree", parent=c)
    nv = E("p:nvGrpSpPr", parent=tree); E("p:cNvPr", {"id": "1", "name": "Shapes"}, nv); E("p:cNvGrpSpPr", parent=nv); E("p:nvPr", parent=nv); E("p:grpSpPr", parent=tree)
    shape(tree, "background", 0, 0, W, H, "navy", "none")
    content(tree)
    return ET.tostring(sld, encoding="utf-8", xml_declaration=True)


def frame(tree, kicker, title, subtitle, n, timing):
    shape(tree, "kicker", 42, 22, 700, 16, None, "none", kicker.upper(), 9, "teal", True)
    shape(tree, "title", 42, 42, 865, 42, None, "none", title, 25, "white", True)
    shape(tree, "subtitle", 42, 88, 865, 26, None, "none", subtitle, 11, "muted")
    shape(tree, "accent", 42, 122, 76, 4, "teal", "none")
    shape(tree, "timing", 820, 22, 98, 16, None, "none", timing, 9, "amber", True, "r")
    shape(tree, "footer", 42, 510, 760, 12, None, "none", "Patagonia Content Studio  |  Card 6.2  |  M7 + M8", 8, "muted")
    shape(tree, "number", 890, 510, 28, 12, None, "none", f"{n:02d}", 8, "muted", False, "r")


def card(tree, x0, y0, w0, h0, head, body, accent="teal", body_size=11):
    shape(tree, head, x0, y0, w0, h0, "panel", "line", None, rounded=True)
    shape(tree, head + " head", x0 + 12, y0 + 10, w0 - 24, 24, None, "none", head, 13, accent, True)
    shape(tree, head + " body", x0 + 12, y0 + 40, w0 - 24, h0 - 50, None, "none", body, body_size, "white")


def s1(tree):
    frame(tree, "Final presentation", "Patagonia Content Studio", "A grounded generator for Instagram, LinkedIn and email", 1, "0:45")
    picture(tree, "rId2", 560, 145, 360, 285, "outdoor header")
    shape(tree, "hero wash", 560, 145, 360, 285, "black", "none")
    shape(tree, "hero label", 590, 178, 290, 22, None, "none", "BRIEF  →  GROUND  →  DRAFT  →  REVIEW", 12, "teal", True)
    shape(tree, "hero copy", 590, 236, 280, 110, None, "none", "Specific enough to verify.\nStructured enough to review.\nHuman approval before export.", 20, "white", True)
    shape(tree, "team", 42, 370, 460, 24, None, "none", "Sergii Rostovskyi  ·  Sandra Obregon  ·  Martha Olukayode", 12, "amber", True)
    shape(tree, "scope", 42, 416, 480, 38, "panel", "line", "English-language Patagonia content studio prototype\nProduct scope: Men's Nano Puff Jacket, style 84212", 11, "white", False, rounded=True)


def s2(tree):
    frame(tree, "01 / Problem", "The content problem has two failure modes", "A small, reviewable workflow keeps fluency from outrunning evidence.", 2, "1:15")
    card(tree, 42, 150, 270, 150, "GENERIC COPY", "Broad language sounds interchangeable.\nReviewers have little to verify.\nSpecific product detail gets lost.", "coral")
    card(tree, 330, 150, 270, 150, "GROUNDING RISK", "Fast generation can blur:\n• product facts\n• secondary context\n• editorial interpretation", "amber")
    card(tree, 618, 150, 300, 150, "CHANNEL FIT", "Instagram, LinkedIn and email\nneed different shapes, limits\nand calls to action.", "blue")
    shape(tree, "qtc label", 42, 330, 100, 20, None, "none", "Q / T / C", 13, "teal", True)
    card(tree, 42, 356, 270, 112, "QUALITY", "Grounded claims\nChannel fit\nTraceable review notes", "teal", 10)
    card(tree, 330, 356, 270, 112, "TIME", "End-to-end demo by Day 2\nWIP capped at 2\nProtect the demo path", "blue", 10)
    card(tree, 618, 356, 300, 112, "COST", "Configurable model\nBounded generation / revision calls\nAgreed team budget: USD 5", "amber", 10)
    shape(tree, "risk", 42, 476, 876, 24, "panel", "line", "TOP RISK  Unsupported or stale claims  |  control: source grounding + peer review + human approval", 10, "coral", True, rounded=True)


def s3(tree):
    frame(tree, "02 / Solution", "Curated sources become channel-specific drafts", "Primary evidence, secondary context and reviewer reasoning stay visibly separate.", 3, "1:30")
    # Architecture flow
    boxes = [(42, "PRIMARY KB", "4 Markdown files\nPatagonia facts + metadata", "teal"), (220, "SECONDARY KB", "2 Markdown files\nTrends + competitor context", "blue"), (398, "LOADER", "Preserves source,\nheading and metadata", "amber"), (576, "PROMPTS", "Instagram · LinkedIn\nEmail-specific shapes", "coral"), (754, "REVIEW", "Notes → edit →\napprove → export", "green")]
    for i, (x0, head, body, ac) in enumerate(boxes):
        card(tree, x0, 150, 164, 106, head, body, ac, 10)
        if i < len(boxes) - 1:
            line(tree, x0 + 164, 203, boxes[i+1][0] - 8, 203, ac)
    shape(tree, "rag title", 42, 284, 220, 20, None, "none", "CURRENT RAG DIRECTION", 12, "teal", True)
    shape(tree, "rag", 42, 310, 510, 82, "panel", "line", "OpenAI embeddings  ·  local SQLite index\nHybrid factual-first retrieval  ·  mutable source UI\nUpload / edit / delete with retrieval provenance", 13, "white", False, rounded=True)
    shape(tree, "trade title", 584, 284, 250, 20, None, "none", "DECISION TRADEOFFS", 12, "amber", True)
    shape(tree, "trade", 584, 310, 334, 82, "panel", "line", "Targeted evidence selection\nSource / version updates\nContext cost + implementation complexity", 12, "white", False, rounded=True)
    shape(tree, "status", 42, 418, 876, 46, "panel", "line", "Evidence boundary  One live Instagram RAG draft reached manual edit, approval and export.\nOther-channel RAG acceptance, live RAG revision and final deployment remain unestablished.", 11, "white", False, rounded=True)
    shape(tree, "source", 42, 478, 876, 16, None, "none", "Historical baseline: deterministic full-context injection fit the small, stable corpus; retrieval is justified by measured scale, diversity, update frequency and review burden.", 9, "muted")


def s4(tree):
    frame(tree, "03 / Live demo", "One brief, one grounded draft, one human review path", "Sergii runs one Instagram generation; Martha makes the review decision.", 4, "2:15")
    steps = [(42, "1  BRIEF", "Enter Instagram brief", "teal"), (214, "2  GENERATE", "One live RAG draft", "blue"), (386, "3  INSPECT", "Copy + notes + provenance", "amber"), (558, "4  EDIT", "Manual edit once", "coral"), (730, "5  APPROVE", "Export Markdown / JSON", "green")]
    for i, (x0, head, body, ac) in enumerate(steps):
        card(tree, x0, 145, 150, 88, head, body, ac, 10)
        if i < len(steps) - 1:
            line(tree, x0 + 150, 189, steps[i+1][0] - 8, 189, ac)
    shape(tree, "preserved", 42, 260, 420, 32, "panel", "line", "Other channels: show preserved state only.\nDo not make extra live calls.", 11, "white", True, rounded=True)
    shape(tree, "fallback", 498, 260, 420, 32, "panel", "line", "API fallback: saved verified artifact, same narrated path.", 11, "white", True, rounded=True)
    shape(tree, "compare", 42, 316, 876, 22, None, "none", "WITHOUT SUPPLIED SOURCES  vs  FULL-CONTEXT INJECTION  —  historical non-RAG comparison", 11, "amber", True, "c")
    card(tree, 42, 350, 420, 112, "WITHOUT SUPPLIED SOURCES", "“Built to pack down easily, it’s designed\nwith convenience in mind”", "coral", 14)
    card(tree, 498, 350, 420, 112, "FULL-CONTEXT INJECTION", "“The internal zippered chest pocket\nthat doubles as a stuffsack”", "teal", 14)
    shape(tree, "demo note", 42, 476, 876, 18, None, "none", "Read the excerpts exactly. One qualitative sample per channel, not statistical proof and not a RAG benchmark.", 9, "muted", False, "c")


def s5(tree):
    frame(tree, "04 / Takeaways", "What we can defend today", "A reviewable prototype with explicit evidence boundaries and a clear next decision set.", 5, "1:15")
    card(tree, 42, 145, 500, 154, "DELIVERED", "• Multi-channel workflow around primary + secondary Markdown KBs\n• Facts, interpretation and reviewer notes stay separate\n• Human approval gates export\n• Historical comparison shows a concrete style-84212 detail", "teal", 11)
    card(tree, 42, 320, 500, 140, "CURRENT RAG STATUS", "Embeddings + local SQLite index + hybrid factual-first retrieval\nMutable-source UI with provenance\nOne live Instagram draft reached edit, approval and export", "blue", 11)
    shape(tree, "limitations", 570, 145, 348, 80, "panel", "line", "LIMITATIONS\nOther-channel RAG acceptance, live RAG revision and final deployment are not established.", 11, "coral", True, rounded=True)
    picture(tree, "rId2", 570, 244, 165, 196, "Day 1 Kanban board")
    picture(tree, "rId3", 753, 244, 165, 196, "Definition of Done")
    shape(tree, "board note", 570, 450, 348, 36, "panel", "line", "Day 1 evidence shown.\nDay 2 board screenshot remains pending.", 10, "amber", True, rounded=True)
    shape(tree, "work", 42, 476, 500, 18, None, "none", "Day 1: plan, source, ingest, smoke-test  |  Day 2: pipeline, UI, evaluation, delivery  |  WIP = 2  |  DoD = artifact + verification + peer review + card record", 9, "white", True)


SLIDES = [s1, s2, s3, s4, s5]
TIMINGS = [45, 75, 90, 135, 75]
NOTES = [
    ("Slide 1 — 0:45 — Martha", "Frame the project as a reviewable company brand generator for three channel formats.\n\nThe goal is an English-language Patagonia studio that drafts from curated source material without inventing facts. Introduce Sergii, Sandra and Martha.\n\nDo not present a final RAG status callout as completed unless the evidence pack confirms it.") ,
    ("Slide 2 — 1:15 — Martha, with Sandra for the KB point", "Connect the problem to the project structure: the team needed a small, reviewable content studio with a human approval step.\n\nForeground the top risk: unsupported or stale claims. The control is primary-source grounding, explicit limitations, peer review and a human approval gate.\n\nMention that Sergii, Sandra, Martha, the hypothetical Patagonia approver and the instructor sit in Quadrant I, high interest and high influence. Keep Q/T/C visible. Do not claim the app eliminates generic language or guarantees factual safety.") ,
    ("Slide 3 — 1:30 — Sandra, with Martha for evaluation", "Explain the architecture progression. The original small, stable corpus justified deterministic full-context injection. Owner-authorized mutable sources and targeted evidence selection motivate the current RAG direction.\n\nCurrent confirmed RAG status: OpenAI embeddings, a local SQLite index, hybrid factual-first retrieval and source upload/edit/delete UI with provenance. Sergii performed the real browser verification: one live Instagram RAG draft was manually reviewed and edited, approved and exported.\n\nDefend the direction using three tradeoffs: targeted evidence selection adds retrieval logic; source/version updates add source-management responsibility; context cost and implementation complexity must be measured. Do not claim lower cost, higher accuracy, or complete channel acceptance.\n\nThe historical comparison is one qualitative sample per channel, not statistical proof.") ,
    ("Slide 4 — 2:15 — Sergii for the app, Martha for the review decision", "Sergii performs the single live browser generation using the approved demo brief. Do not promise a particular model response.\n\nPoint out channel copy, separate reviewer notes and preserved retrieval provenance. Show the human gate: manual edit, approval of the exact current revision, then Markdown/JSON export.\n\nIf the API fails, use the saved verified artifact. Do not make extra live calls for LinkedIn or email.\n\nRead the exact matched excerpts aloud and label the experiment “Without supplied sources vs full-context injection — historical non-RAG comparison.” Do not call it a RAG benchmark or a comparison with the ChatGPT product.\n\nThe preserved format observations are one qualitative sample per channel: Instagram 70 vs 81 words, LinkedIn generic 116 below minimum vs contextual 135 OK, and email generic 107 vs contextual 133 under the clarification convention. Do not add scores.") ,
    ("Slide 5 — 1:15 — Martha, with Sandra and Sergii available for questions", "Contrast the board checkpoints. Day 1 evidence includes the actual Kanban screenshot and supplementary Definition of Done screenshot. The actual Day 2 board screenshot remains pending.\n\nExplain the WBS-to-Trello bridge: each WBS leaf became a card with owner, reviewer, Must IDs, dependencies and verification. Card 6.2 owns the final docs, demo and presentation.\n\nMention the lessons: start with a bounded corpus, add retrieval when mutable sources and targeted evidence selection justify the complexity, keep reviewer reasoning visible, protect the demo path with WIP=2, and treat comparison artifacts as evidence with explicit limits.\n\nState the evidence boundary clearly: Sergii’s one verified Instagram RAG path is real and specific. Other-channel RAG acceptance, live RAG revision and final deployment are not established. Martha read agents.md before this revision and kept the change to presentation artifacts only.") ,
]


def rels(items):
    root = E("Relationships", {"xmlns": NS["rel"]})
    for rid, typ, target in items:
        E("Relationship", {"Id": rid, "Type": typ, "Target": target}, root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def notes_xml(note_text: str, slide_num: int):
    # Notes slides are intentionally simple but valid OOXML so PowerPoint exposes the speaker notes.
    root = E("p:notes", {"xmlns:a": NS["a"], "xmlns:r": NS["r"], "xmlns:p": NS["p"]})
    c = E("p:cSld", parent=root); tree = E("p:spTree", parent=c)
    nv = E("p:nvGrpSpPr", parent=tree); E("p:cNvPr", {"id": "1", "name": "Notes"}, nv); E("p:cNvGrpSpPr", parent=nv); E("p:nvPr", parent=nv); E("p:grpSpPr", parent=tree)
    sp = E("p:sp", parent=tree); n = E("p:nvSpPr", parent=sp); E("p:cNvPr", {"id": "2", "name": "Speaker Notes"}, n); E("p:cNvSpPr", parent=n); E("p:nvPr", parent=n)
    sppr = E("p:spPr", parent=sp); xf = E("a:xfrm", parent=sppr); E("a:off", {"x": "0", "y": "0"}, xf); E("a:ext", {"cx": str(6858000), "cy": str(9144000)}, xf); geom = E("a:prstGeom", {"prst": "rect"}, sppr); E("a:avLst", parent=geom); E("a:noFill", parent=sppr); E("a:noFill", parent=E("a:ln", parent=sppr))
    text_body(sp, note_text, 12, "000000")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build():
    OUT.mkdir(exist_ok=True)
    content_types = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/><Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/><Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/><Override PartName="/ppt/notesMasters/notesMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"/><Override PartName="/ppt/notesMasters/_rels/notesMaster1.xml.rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>']
    for i in range(1, 6):
        content_types += [f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>', f'<Override PartName="/ppt/notesSlides/notesSlide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>']
    content_types.append('</Types>')
    presentation = '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>' + ''.join(f'<p:sldId id="{255+i}" r:id="rId{i+1}"/>' for i in range(1, 6)) + '</p:sldIdLst><p:sldSz cx="12192000" cy="6858000" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
    root_rels = rels([('rId1', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument', 'ppt/presentation.xml')])
    pres_rels = [('rId1', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster', 'slideMasters/slideMaster1.xml')]
    pres_rels += [(f'rId{i+1}', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide', f'slides/slide{i}.xml') for i in range(1, 6)]
    theme = '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Patagonia Content Studio"><a:themeElements><a:clrScheme name="Custom"><a:dk1><a:srgbClr val="0B1220"/></a:dk1><a:lt1><a:srgbClr val="F8FAFC"/></a:lt1><a:dk2><a:srgbClr val="111C2E"/></a:dk2><a:lt2><a:srgbClr val="A8B5C7"/></a:lt2><a:accent1><a:srgbClr val="5EEAD4"/></a:accent1><a:accent2><a:srgbClr val="60A5FA"/></a:accent2><a:accent3><a:srgbClr val="FBBF24"/></a:accent3><a:accent4><a:srgbClr val="FB7185"/></a:accent4><a:accent5><a:srgbClr val="86EFAC"/></a:accent5></a:clrScheme><a:fontScheme name="Aptos"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme><a:fmtScheme name="Custom"><a:fillStyleLst><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:fillStyleLst><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst><a:solidFill><a:srgbClr val="0B1220"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>'
    master = '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld name="Master"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name="Master"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" hlink="accent2" folHlink="accent4"/><p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>'
    layout = '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name="Layout"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'
    notes_master = '<p:notesMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld name="Notes Master"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name="Notes Master"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:hf dt="0" ftr="0" sldNum="0"/><p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" hlink="accent2" folHlink="accent4" tx1="dk1" tx2="dk2" bg1="lt1" bg2="lt2"/></p:notesMaster>'
    with zipfile.ZipFile(PPTX, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ''.join(content_types)); z.writestr('_rels/.rels', root_rels); z.writestr('ppt/presentation.xml', presentation); z.writestr('ppt/_rels/presentation.xml.rels', rels(pres_rels)); z.writestr('ppt/theme/theme1.xml', theme); z.writestr('ppt/slideMasters/slideMaster1.xml', master); z.writestr('ppt/slideMasters/_rels/slideMaster1.xml.rels', rels([('rId1', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout', '../slideLayouts/slideLayout1.xml'), ('rId2', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme', '../theme/theme1.xml')])); z.writestr('ppt/slideLayouts/slideLayout1.xml', layout); z.writestr('ppt/slideLayouts/_rels/slideLayout1.xml.rels', rels([('rId1', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster', '../slideMasters/slideMaster1.xml')])); z.writestr('ppt/notesMasters/notesMaster1.xml', notes_master); z.writestr('ppt/notesMasters/_rels/notesMaster1.xml.rels', rels([('rId1', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme', '../theme/theme1.xml')]))
        for i, fn in enumerate(SLIDES, 1):
            img_rels = [('rId1', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout', '../slideLayouts/slideLayout1.xml'), ('rId9', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide', f'../notesSlides/notesSlide{i}.xml')]
            if i == 1:
                z.write(ROOT / 'assets' / 'outdoor-header-v1.png', 'ppt/media/outdoor.png'); img_rels.append(('rId2', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image', '../media/outdoor.png'))
            if i == 5:
                z.write(ROOT / 'docs' / 'evidence' / 'p2-kanban-day1.png', 'ppt/media/kanban.png'); z.write(ROOT / 'docs' / 'evidence' / 'p2-kanban-day1-dod.png', 'ppt/media/dod.png'); img_rels.extend([('rId2', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image', '../media/kanban.png'), ('rId3', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image', '../media/dod.png')])
            z.writestr(f'ppt/slides/slide{i}.xml', slide_xml(fn)); z.writestr(f'ppt/slides/_rels/slide{i}.xml.rels', rels(img_rels))
            z.writestr(f'ppt/notesSlides/notesSlide{i}.xml', notes_xml(NOTES[i-1][0] + "\n\n" + NOTES[i-1][1], i))
            z.writestr(f'ppt/notesSlides/_rels/notesSlide{i}.xml.rels', rels([('rId1', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide', f'../slides/slide{i}.xml'), ('rId2', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster', '../notesMasters/notesMaster1.xml')]))
    (OUT / 'speaker_notes.md').write_text('# Speaker notes — Patagonia Content Studio Final\n\n' + '\n\n'.join(f'## {h}\n\n{b}' for h, b in NOTES) + '\n\nTotal speaking time: 7:00. Maximum including contingency: 8:00.\n', encoding='utf-8')
    (OUT / 'demo_runbook.md').write_text('''# Demo runbook — Patagonia Content Studio\n\n## Timing and owners\n\n- Slide 4 demo block: 2:15. Sergii runs the app; Martha makes the review decision.\n- Total presentation timing: 0:45 + 1:15 + 1:30 + 2:15 + 1:15 = 7:00.\n- Maximum with contingency: 8:00.\n\n## Before presenting\n\n1. Open the Streamlit app with the configured local environment.\n2. Confirm the approved demo brief is ready and that no secret is visible.\n3. Have the saved verified Instagram artifact available as fallback.\n4. Open the preserved LinkedIn and email acceptance artifacts for reference only.\n5. Keep the Day 1 Kanban and Definition of Done evidence available.\n\n## Live sequence\n\n1. Enter the Instagram brief in Streamlit.\n2. Generate exactly one Instagram draft live with RAG retrieval.\n3. Point out channel copy, separate reviewer notes, and retrieval provenance.\n4. Manually edit the draft once.\n5. Approve the exact edited revision.\n6. Show Markdown and JSON export.\n\n## Guardrails\n\n- Do not make extra live calls for LinkedIn or email. Show preserved state only.\n- Do not promise a particular model response.\n- Keep reviewer notes separate from publishable copy.\n- Do not claim all-channel RAG acceptance, live RAG revision, final deployment, cost savings, or accuracy gains.\n- Read the historical excerpts exactly and label them: **Without supplied sources vs full-context injection — historical non-RAG comparison**.\n\n## Fallback\n\nIf the API fails, use the saved verified artifact and narrate the same review, approval, and export path. The saved artifact demonstrates the approved Instagram flow and preserves revision, fingerprint, and provenance evidence.\n''', encoding='utf-8')
    print(f"{PPTX} | slides={len(SLIDES)} | seconds={sum(TIMINGS)}")


if __name__ == "__main__":
    build()
