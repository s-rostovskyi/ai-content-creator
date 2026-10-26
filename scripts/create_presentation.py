from __future__ import annotations

import html
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "presentation_output"
OUT.mkdir(exist_ok=True)
PPTX = OUT / "AI_Content_Creator_Presentation.pptx"

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
COLORS = {"navy": "0B1220", "panel": "111C2E", "white": "F8FAFC", "muted": "A8B5C7", "teal": "5EEAD4", "blue": "60A5FA", "amber": "FBBF24", "coral": "FB7185", "green": "86EFAC", "line": "263650"}


def x(v: float) -> int:
    return int(v / W * 13.333333 * EMU)


def y(v: float) -> int:
    return int(v / H * 7.5 * EMU)


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def elem(tag: str, attrs: dict | None = None, parent=None):
    e = ET.Element(tag, attrs or {}) if parent is None else ET.SubElement(parent, tag, attrs or {})
    return e


def solid_fill(parent, color: str):
    sf = elem("a:solidFill", parent=parent)
    elem("a:srgbClr", {"val": COLORS.get(color, color)}, sf)


def tx_body(parent, text: str, size: int, color: str, bold=False, align="l"):
    tb = elem("p:txBody", parent=parent)
    elem("a:bodyPr", {"wrap": "square", "anchor": "t"}, tb)
    elem("a:lstStyle", parent=tb)
    for i, line in enumerate(text.split("\n")):
        p = elem("a:p", parent=tb)
        if align != "l":
            elem("a:pPr", {"algn": {"c": "ctr", "r": "r"}.get(align, "l")}, p)
        r = elem("a:r", parent=p)
        rpr = elem("a:rPr", {"lang": "en-US", "sz": str(size * 100), "b": "1" if bold else "0"}, r)
        solid_fill(rpr, color)
        elem("a:t", parent=r).text = line
        if i < len(text.split("\n")) - 1:
            elem("a:endParaRPr", {"lang": "en-US"}, p)
    return tb


def shape(sp_tree, name, x0, y0, w0, h0, fill=None, line="line", text=None, size=12, color="white", bold=False, align="l", rounded=False):
    sp = elem("p:sp", parent=sp_tree)
    nv = elem("p:nvSpPr", parent=sp)
    elem("p:cNvPr", {"id": str(100 + len(list(sp_tree))), "name": name}, nv)
    elem("p:cNvSpPr", parent=nv)
    elem("p:nvPr", parent=nv)
    sppr = elem("p:spPr", parent=sp)
    xfrm = elem("a:xfrm", parent=sppr)
    elem("a:off", {"x": str(x(x0)), "y": str(y(y0))}, xfrm)
    elem("a:ext", {"cx": str(x(w0)), "cy": str(y(h0))}, xfrm)
    geom = "roundRect" if rounded else "rect"
    geom_el = elem("a:prstGeom", {"prst": geom}, sppr)
    elem("a:avLst", parent=geom_el)
    if fill:
        solid_fill(sppr, fill)
    else:
        elem("a:noFill", parent=sppr)
    ln = elem("a:ln", {"w": "12000"}, sppr)
    if line == "none":
        elem("a:noFill", parent=ln)
    else:
        solid_fill(ln, line)
    if text is not None:
        tx_body(sp, text, size, color, bold, align)
    return sp


def line(sp_tree, x1, y1, x2, y2, color="teal"):
    sp = elem("p:sp", parent=sp_tree)
    nv = elem("p:nvSpPr", parent=sp); elem("p:cNvPr", {"id": str(100 + len(list(sp_tree))), "name": "connector"}, nv); elem("p:cNvSpPr", parent=nv); elem("p:nvPr", parent=nv)
    sppr = elem("p:spPr", parent=sp)
    xfrm = elem("a:xfrm", parent=sppr); elem("a:off", {"x": str(x(x1)), "y": str(y(y1))}, xfrm); elem("a:ext", {"cx": str(x(x2-x1)), "cy": str(y(y2-y1))}, xfrm)
    geom = elem("a:prstGeom", {"prst": "line"}, sppr); elem("a:avLst", parent=geom)
    ln = elem("a:ln", {"w": "14000"}, sppr); solid_fill(ln, color); elem("a:tailEnd", {"type": "triangle"}, ln)


def picture(sp_tree, rel_id, x0, y0, w0, h0):
    pic = elem("p:pic", parent=sp_tree)
    nv = elem("p:nvPicPr", parent=pic); elem("p:cNvPr", {"id": str(900 + len(list(sp_tree))), "name": "kanban evidence"}, nv); elem("p:cNvPicPr", parent=nv); elem("p:nvPr", parent=nv)
    blip = elem("p:blipFill", parent=pic); elem("a:blip", {"{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed": rel_id}, blip); elem("a:stretch", parent=blip).append(elem("a:fillRect"))
    sppr = elem("p:spPr", parent=pic); xfrm = elem("a:xfrm", parent=sppr); elem("a:off", {"x": str(x(x0)), "y": str(y(y0))}, xfrm); elem("a:ext", {"cx": str(x(w0)), "cy": str(y(h0))}, xfrm); geom = elem("a:prstGeom", {"prst": "rect"}, sppr); elem("a:avLst", parent=geom)


def slide_xml(content, image=False):
    sld = elem("p:sld", {"showMasterSp": "0", "xmlns:a": NS["a"], "xmlns:p": NS["p"], "xmlns:r": NS["r"]}); c = elem("p:cSld", parent=sld); tree = elem("p:spTree", parent=c)
    nv = elem("p:nvGrpSpPr", parent=tree); elem("p:cNvPr", {"id": "1", "name": "Shapes"}, nv); elem("p:cNvGrpSpPr", parent=nv); elem("p:nvPr", parent=nv)
    elem("p:grpSpPr", parent=tree)
    shape(tree, "background", 0, 0, W, H, "navy", "none")
    content(tree)
    return ET.tostring(sld, encoding="utf-8", xml_declaration=True)


def make_content(eyebrow, title, subtitle, cards=(), footer="AI Content Creator", extra=None):
    def fn(tree):
        shape(tree, "eyebrow", 42, 22, 800, 16, None, "none", eyebrow.upper(), 9, "teal", True)
        shape(tree, "title", 42, 42, 870, 40, None, "none", title, 26, "white", True)
        shape(tree, "subtitle", 42, 88, 870, 24, None, "none", subtitle, 11, "muted")
        shape(tree, "accent", 42, 122, 78, 4, "teal", "none")
        for card in cards:
            cx, cy, cw, ch, head, body, accent = card
            shape(tree, head, cx, cy, cw, ch, "panel", "line", None, rounded=True)
            shape(tree, head + " head", cx + 10, cy + 9, cw - 20, 23, None, "none", head, 14, accent, True)
            shape(tree, head + " body", cx + 10, cy + 38, cw - 20, ch - 46, None, "none", body, 10, "white")
        if extra:
            extra(tree)
        shape(tree, "footer", 42, 505, 760, 14, None, "none", footer, 8, "muted")
        shape(tree, "number", 890, 505, 28, 14, None, "none", str(make_content.slide_no).zfill(2), 8, "muted", False, "r")
    return fn


def build_slides():
    slides = []
    def add(fn):
        make_content.slide_no += 1
        slides.append(fn)
    make_content.slide_no = 0
    def title(tree):
        shape(tree, "brand", 58, 58, 500, 18, None, "none", "AI CONTENT CREATOR", 11, "teal", True)
        shape(tree, "title", 58, 112, 650, 170, None, "none", "Intelligent,\nBrand-Aware\nContent Generation", 35, "white", True)
        shape(tree, "sub", 62, 316, 560, 55, None, "none", "A grounded Patagonia Content Studio prototype\nthat turns a campaign brief into reviewable, channel-native drafts.", 15, "muted")
        shape(tree, "stack", 62, 420, 620, 24, None, "none", "Python • Streamlit • Markdown knowledge bases • OpenAI API", 11, "amber", True)
        shape(tree, "date", 62, 466, 500, 18, None, "none", "22–23 October 2026  |  Final project presentation", 9, "muted")
    add(title)
    add(make_content("01 / Product", "The product is a controlled path from brief to publishable draft", "The system is an intelligent interface between a marketing team and its prospective customers.", [(52,170,210,150,"1. BRIEF","A human enters the campaign goal, audience and channel.","teal"),(275,170,210,150,"2. GROUND","Curated primary + secondary Markdown sources are assembled deterministically.","blue"),(498,170,210,150,"3. DRAFT","OpenAI generates a channel-specific draft with reviewer notes.","amber"),(721,170,185,150,"4. REVIEW","Edit, revise, approve and export — only after human action.","coral")]))
    add(make_content("02 / Why now", "The problem is not “can AI write?” — it is “can a brand stay itself?”", "Generic AI-Slop creates copy that is smooth, interchangeable and weakly accountable.", [(55,165,250,205,"GENERIC AI-SLOP","• Broad slogans\n• Homogenized tone\n• Unclear source of truth\n• Unsupported claims hide in fluent copy","coral"),(355,165,250,205,"BUSINESS COST","• Weak differentiation\n• Inconsistent brand identity\n• More reviewer rework\n• Slower path to approved copy","amber"),(655,165,250,205,"DESIGN RESPONSE","• Two curated knowledge bases\n• Prompt-level grounding rules\n• Channel-native templates\n• Human review as a hard gate","teal")], extra=lambda t: shape(t,"takeaway",75,410,800,35,None,"none","Distinctive because it is specific, useful and traceable — not because it is “creative” in the abstract.",16,"white",True,"c")))
    add(make_content("03 / Strategy", "A small, explicit operating model keeps the prototype honest", "Quality, Time and Cost are treated as constraints — not afterthoughts.", [(52,155,270,155,"QUALITY","Grounded in verified source notes\nDistinct channel tone\nClaim traceability\nObvious UI states","teal"),(345,155,270,155,"TIME","Two-day end-to-end demo\nAt most two active cards\nPair/review work protects flow\nDay 2 demo path first","blue"),(638,155,270,155,"COST","Configurable model\nBound generation/revision calls\nUsage captured when available\nAgreed team budget: USD 5","amber")], extra=lambda t: (shape(t,"stake",52,350,820,58,None,"none","Stakeholders\nSergii · technical lead    Sandra · primary KB owner    Martha · evaluation/usability reviewer",13,"white"),shape(t,"risk",52,430,830,24,None,"none","Top risk: unsupported or stale claims  →  source-grounding + peer review + approval gate",14,"coral",True))))
    add(make_content("04 / Delivery", "The WBS maps directly to the Kanban path", "Planning closure precedes development; the team protects a two-card WIP limit.", [(46,160,160,220,"PLAN","1.1 Board alignment","teal"),(226,160,160,220,"KNOWLEDGE","2.1 Primary KB\n2.2 Secondary KB","blue"),(406,160,160,220,"GENERATION","3.1 Ingestion\n3.2 Context + RAG\n4.1 OpenAI\n4.2 Templates\n4.3 Pipeline","amber"),(586,160,160,220,"INTERFACE + EVAL","5.1 Streamlit\n5.2 Uniqueness","coral"),(766,160,160,220,"DELIVERY","6.1 Runtime\n6.2 Docs + demo","green")], extra=lambda t: shape(t,"rule",52,414,840,28,None,"none","Maximum two active cards team-wide; every card needs an owner, reviewer, Must ID and verification evidence.",14,"white",True,"c")))
    add(make_content("05 / Knowledge", "Two knowledge bases separate authority from context", "The distinction prevents competitor or trend material from becoming an accidental Patagonia fact.", [(52,162,340,230,"PRIMARY / PATAGONIA EVIDENCE","4 Markdown documents\n\nBrand voice observations\nPublished examples\nProduct facts — style 84212\nCare, repair and reuse\n\nAuthority for Patagonia claims","teal"),(568,162,340,230,"SECONDARY / INDUSTRY CONTEXT","2 Markdown documents\n\nCompetitor context\nOutdoor participation + textile reuse\n\nPositioning input only\nNever transfer competitor features or claims to Patagonia","blue")], extra=lambda t: shape(t,"flow",128,427,700,26,None,"none","Markdown → parser → metadata + sections → deterministic context bundle → prompt",15,"white",True,"c")))
    add(make_content("06 / Architecture decision", "RAG was consciously deferred — and measured conditions are defined", "Current implementation: fixed, deterministic context injection. No query-based retrieval, embeddings or vector store.", [(52,158,255,230,"WHY THIS FITS NOW","Small, stable corpus\nReviewable baseline\nTwo-day schedule\nBounded source inclusion\nSimple failure modes","teal"),(352,158,255,230,"WHAT IS IMPLEMENTED","Loads 6 curated Markdown files\nSerializes primary + secondary contexts\n14,474 serialized characters\n40,000-character guardrail\nOne smoke-test request: 4,230 tokens","blue"),(652,158,255,230,"WHEN TO REVISIT","Corpus grows or overlaps\nFrequent updates\nMore diverse briefs\nMeasured token/latency burden\nReview burden makes fixed inclusion inefficient","amber")], extra=lambda t: shape(t,"decision",82,425,790,28,None,"none","RAG becomes justified by measured corpus size, request diversity, update frequency and context limits.",15,"white",True,"c")))
    add(make_content("07 / Technical flow", "From Markdown sources to a reviewable draft", "The pipeline is intentionally inspectable at each boundary.", [(45,175,160,170,"INGEST","document_processor.py\nParse Markdown; validate metadata; preserve sections","teal"),(225,175,160,170,"ASSEMBLE","knowledge_base.py\nBuild deterministic primary + secondary context","blue"),(405,175,160,170,"PROMPT","prompt_templates.py\nApply grounding, channel constraints and anti-slop rules","amber"),(585,175,160,170,"GENERATE","llm_integration.py\nCall configurable OpenAI model; capture usage","coral"),(765,175,160,170,"REVIEW","content_pipeline.py\nFeedback, revision, edit, approval and export","green")], extra=lambda t: shape(t,"gate",52,400,820,28,None,"none","Human gate: the draft cannot become approved/exported content without explicit confirmation of the exact revision.",14,"white",True,"c")))
    add(make_content("08 / Demonstration", "The working application demo follows one visible state machine", "Demo path: load campaign → generate → revise/edit → approve → export.", [(52,158,190,245,"CAMPAIGN","Channel selector\nBrief text area\nLoad campaign\n\nImplemented in app.py","teal"),(267,158,190,245,"DRAFT","Generate draft\nChannel copy\nReviewer notes\nResponse metadata","blue"),(482,158,190,245,"REVIEW","Feedback for revision\nManual edit\nSave edit\nApproval checkbox\nDirty edits block approval","amber"),(697,158,210,245,"EXPORT","Approve exact revision\nDownload Markdown\nDownload JSON metadata\nHuman action required","coral")], extra=lambda t: shape(t,"status",55,435,850,28,None,"none","Evidence status: Instagram path manually verified; LinkedIn/email live checks pending. No application screenshot is present in the repository.",12,"muted",False,"c")))
    add(make_content("09 / Uniqueness", "The evaluation shows why context beats generic fluency", "The evidence is a first-pass fixture comparison, not a claim about live model performance.", [(55,165,355,220,"GENERIC FIXTURE — FAILED","“Elevate your everyday adventure with a game-changer.”\n\nNo Patagonia context\nFlags: “elevate your” + “game-changer”","coral"),(550,165,355,220,"CONTEXTUAL FIXTURE — PASSED","Names the Nano Puff jacket\nConnects to a changing forecast\nIncludes repair + reuse guidance\nNo flagged generic phrases","teal")], extra=lambda t: shape(t,"contract",55,418,830,22,None,"none","Specificity  ·  Productive tension  ·  Channel-native writing  ·  Anti-slop control",14,"white",True,"c")))
    add(make_content("10 / Prompting", "Advanced prompting turns brand intent into testable constraints", "The system does not ask the model to “be creative”; it specifies what good looks like and what must not happen.", [(52,158,270,235,"GROUNDING","Primary is authoritative\nSecondary is positioning only\nSeparate facts from interpretation\nPreserve limitations and dates","teal"),(345,158,270,235,"CHANNEL SHAPE","Instagram: 60–120 words\nLinkedIn: 120–200 words\nEmail: subject/preheader/body limits\nOne CTA; format-native rhythm","blue"),(638,158,270,235,"ANTI-SLOP","Avoid cliches and superlatives\nNo vague sustainability claims\nNo invented facts\nReturn copy + reviewer notes","coral")], extra=lambda t: shape(t,"inspectable",80,425,800,26,None,"none","Prompt output is inspectable: source paths/URLs, facts used, interpretations and unresolved limitations.",14,"white",True,"c")))
    add(make_content("11 / Implementation", "The technical spine is small enough to inspect end-to-end", "Repository structure, configuration and AGENTS.md are part of the product discipline.", [(52,155,255,255,"DOCUMENT PROCESSING","src/document_processor.py\nMarkdownIt parser\nRequired metadata schema\nHeading-path sections\nSource URLs + access dates","teal"),(352,155,255,255,"INTEGRATION","src/llm_integration.py\nOPENAI_API_KEY\nOPENAI_MODEL\nUsage capture when available\nNo secrets logged","blue"),(652,155,255,255,"DELIVERY SURFACE","app.py — Streamlit\nsrc/main.py — CLI\ntemplates/*.md\noutputs/ — approved exports\ntests/ — automated checks","amber")], extra=lambda t: shape(t,"agents",60,435,840,28,None,"none","AGENTS.md keeps scope explicit: Must IDs M1–M8, human approval, no fabricated facts, no secrets and no unapproved scope expansion.",13,"white",True,"c")))
    add(make_content("12 / Learning", "The hard parts were control problems, not syntax problems", "The project’s solutions are boundary decisions: what to include, what to exclude, and how to prove it.", [(52,158,265,230,"CHALLENGE","Grounding without retrieval\nSmall corpus, mixed authority\nRisk of context leakage","coral"),(347,158,265,230,"SOLUTION","Separate primary/secondary\nDeterministic bundle\nMetadata + section traceability\nMeasured revisit conditions","teal"),(642,158,265,230,"LESSON","Do not infer RAG need from hype\nDo not call a fixture a benchmark\nHuman review remains part of the system","amber")], extra=lambda t: shape(t,"lesson",85,425,790,26,None,"none","A strong prototype can say “not measured yet” — as long as it records what would change the decision.",15,"white",True,"c")))
    def kanban(tree):
        base = make_content("13 / Kanban evidence", "Day 1 made the work visible; Day 2 turned it into a demo path", "Actual Day 1 board evidence is preserved in the repository.", [])
        base(tree)
        shape(tree,"note",580,155,325,135,"panel","line",None,rounded=True); shape(tree,"h",590,164,305,23,None,"none","DAY 1 — VERIFIED",14,"teal",True); shape(tree,"b",590,196,305,80,None,"none","Planning, KBs, loader, context injection, templates, offline integration, live Instagram smoke test; 62 offline tests passed.",10,"white")
        shape(tree,"note2",580,315,325,135,"panel","line",None,rounded=True); shape(tree,"h2",590,324,305,23,None,"none","DAY 2 — TARGET / STATUS",14,"amber",True); shape(tree,"b2",590,356,305,80,None,"none","Pipeline, UI, review/export, evaluation, docs and presentation. Instagram path manually verified; LinkedIn/email live checks remain pending.",10,"white")
        img = ROOT / "docs" / "evidence" / "p2-kanban-day1.png"
        if img.exists(): picture(tree, "rId2", 55, 150, 485, 300)
        shape(tree,"source",55,462,485,18,None,"none","Screenshot source: docs/evidence/p2-kanban-day1.png",9,"muted")
    add(kanban)
    add(make_content("14 / Outcomes", "What exists now — and what remains deliberately open", "The outcome is a grounded, reviewable prototype with a clear next decision set.", [(52,155,260,240,"IMPLEMENTED","Two KBs + metadata\nDeterministic context\nThree channel templates\nOpenAI integration\nCLI + Streamlit flow\nHuman approval/export","teal"),(350,155,260,240,"LIMITATIONS","No RAG / vector store\nNo automated publishing\nNo auth/database/scheduling\nCost not calculated\nLinkedIn/email live checks pending\nNo production deployment evidence","coral"),(648,155,260,240,"NEXT DEVELOPMENT","Preserve live generic/contextual outputs\nMeasure repeated-request burden\nRevisit retrieval when evidence says so\nAdd broader runtime validation\nCapture application screenshots","amber")]))
    def close(tree):
        shape(tree,"brand",83,180,130,20,None,"none","BRIEF",11,"teal",True, "c"); shape(tree,"ground",260,180,130,20,None,"none","GROUND",11,"blue",True,"c"); shape(tree,"draft",438,180,130,20,None,"none","DRAFT",11,"amber",True,"c"); shape(tree,"review",615,180,130,20,None,"none","REVIEW",11,"coral",True,"c"); shape(tree,"approve",792,180,90,20,None,"none","APPROVE",11,"green",True,"c"); shape(tree,"take",260,265,440,26,None,"none","One clear takeaway",17,"white",True,"c"); shape(tree,"copy",165,305,630,60,None,"none","Specificity + source discipline + channel-native prompting\nmake the output more distinguishable and more reviewable.",21,"teal",True,"c"); shape(tree,"thanks",400,430,160,24,None,"none","Thank you",13,"muted",False,"c"); shape(tree,"footer",42,505,760,14,None,"none","AI Content Creator — Patagonia Content Studio",8,"muted")
    add(close)
    return slides


def rels(items):
    root = elem("Relationships", {"xmlns": NS["rel"]})
    for rid, typ, target in items:
        elem("Relationship", {"Id": rid, "Type": typ, "Target": target}, root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_pptx():
    slides = build_slides()
    content_types = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/><Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/><Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>']
    for i in range(1, len(slides)+1): content_types.append(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
    content_types.append('</Types>')
    presentation = '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>' + ''.join(f'<p:sldId id="{255+i}" r:id="rId{i+2}"/>' for i in range(1,len(slides)+1)) + '</p:sldIdLst><p:sldSz cx="12192000" cy="6858000" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
    root_rels = rels([('rId1','http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument','ppt/presentation.xml')])
    pres_rels = [('rId1','http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster','slideMasters/slideMaster1.xml')]
    pres_rels += [(f'rId{i+1}','http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide',f'slides/slide{i}.xml') for i in range(1,len(slides)+1)]
    theme = '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="AI Content Creator"><a:themeElements><a:clrScheme name="Custom"><a:dk1><a:srgbClr val="0B1220"/></a:dk1><a:lt1><a:srgbClr val="F8FAFC"/></a:lt1><a:dk2><a:srgbClr val="111C2E"/></a:dk2><a:lt2><a:srgbClr val="A8B5C7"/></a:lt2><a:accent1><a:srgbClr val="5EEAD4"/></a:accent1><a:accent2><a:srgbClr val="60A5FA"/></a:accent2><a:accent3><a:srgbClr val="FBBF24"/></a:accent3><a:accent4><a:srgbClr val="FB7185"/></a:accent4><a:accent5><a:srgbClr val="86EFAC"/></a:accent5><a:accent6><a:srgbClr val="263650"/></a:accent6><a:hlink><a:srgbClr val="60A5FA"/></a:hlink><a:folHlink><a:srgbClr val="FB7185"/></a:folHlink></a:clrScheme><a:fontScheme name="Aptos"><a:majorFont><a:latin typeface="Aptos Display"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme><a:fmtScheme name="Custom"><a:fillStyleLst><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:srgbClr val="0B1220"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>'
    master = '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld name="Master"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name="Master"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>'
    layout = '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name="Layout"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'
    with zipfile.ZipFile(PPTX, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',''.join(content_types)); z.writestr('_rels/.rels',root_rels); z.writestr('ppt/presentation.xml',presentation); z.writestr('ppt/_rels/presentation.xml.rels',rels(pres_rels)); z.writestr('ppt/theme/theme1.xml',theme); z.writestr('ppt/slideMasters/slideMaster1.xml',master); z.writestr('ppt/slideMasters/_rels/slideMaster1.xml.rels',rels([('rId1','http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout','../slideLayouts/slideLayout1.xml'),('rId2','http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme','../theme/theme1.xml')])); z.writestr('ppt/slideLayouts/slideLayout1.xml',layout); z.writestr('ppt/slideLayouts/_rels/slideLayout1.xml.rels',rels([('rId1','http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster','../slideMasters/slideMaster1.xml')]))
        for i, fn in enumerate(slides, 1):
            xml = slide_xml(fn, i == 14); z.writestr(f'ppt/slides/slide{i}.xml', xml)
            items = [('rId1','http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout','../slideLayouts/slideLayout1.xml')]
            if i == 14:
                img = ROOT / 'docs' / 'evidence' / 'p2-kanban-day1.png'
                if img.exists(): z.write(img, 'ppt/media/kanban.png'); items.append(('rId2','http://schemas.openxmlformats.org/officeDocument/2006/relationships/image','../media/kanban.png'))
            z.writestr(f'ppt/slides/_rels/slide{i}.xml.rels', rels(items))


if __name__ == '__main__':
    write_pptx()
    print(PPTX)
