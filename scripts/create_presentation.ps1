$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$outDir = Join-Path $root 'presentation_output'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$pptxPath = Join-Path $outDir 'AI_Content_Creator_Presentation.pptx'
$pdfPath = Join-Path $outDir 'AI_Content_Creator_Presentation.pdf'

$ppLayoutBlank = 12
$msoTrue = -1
$msoFalse = 0
$ppSaveAsOpenXMLPresentation = 24
$ppFixedFormatTypePDF = 2
$ppFixedFormatIntentScreen = 1
$msoTextOrientationHorizontal = 1
$msoShapeRectangle = 1
$msoShapeRoundedRectangle = 5
$msoShapeLine = 9
$msoShapeChevron = 52
$msoShapeHexagon = 10
$msoShapeOval = 9
$msoArrowheadTriangle = 3
$ppAlignLeft = 1
$ppAlignCenter = 2
$ppAlignRight = 3
$msoAnchorTop = 1
$msoAnchorMiddle = 3

Add-Type -AssemblyName System.Drawing

$navy = [System.Drawing.ColorTranslator]::ToOle('#0B1220')
$panel = [System.Drawing.ColorTranslator]::ToOle('#111C2E')
$panel2 = [System.Drawing.ColorTranslator]::ToOle('#16243A')
$white = [System.Drawing.ColorTranslator]::ToOle('#F8FAFC')
$muted = [System.Drawing.ColorTranslator]::ToOle('#A8B5C7')
$teal = [System.Drawing.ColorTranslator]::ToOle('#5EEAD4')
$coral = [System.Drawing.ColorTranslator]::ToOle('#FB7185')
$amber = [System.Drawing.ColorTranslator]::ToOle('#FBBF24')
$blue = [System.Drawing.ColorTranslator]::ToOle('#60A5FA')
$green = [System.Drawing.ColorTranslator]::ToOle('#86EFAC')
$line = [System.Drawing.ColorTranslator]::ToOle('#263650')

function Add-Text($slide, [string]$text, [float]$x, [float]$y, [float]$w, [float]$h, [float]$size, $color, [bool]$bold=$false, [int]$align=$ppAlignLeft, [string]$font='Aptos') {
    $shape = $slide.Shapes.AddTextbox($msoTextOrientationHorizontal, $x, $y, $w, $h)
    $shape.TextFrame2.TextRange.Text = $text
    $shape.TextFrame2.TextRange.Font.Name = $font
    $shape.TextFrame2.TextRange.Font.Size = $size
    $shape.TextFrame2.TextRange.Font.Bold = $(if ($bold) { $msoTrue } else { $msoFalse })
    $shape.TextFrame2.TextRange.Font.Fill.ForeColor.RGB = $color
    $shape.TextFrame2.TextRange.ParagraphFormat.Alignment = $align
    $shape.TextFrame2.VerticalAnchor = $msoAnchorTop
    $shape.TextFrame2.MarginLeft = 2
    $shape.TextFrame2.MarginRight = 2
    $shape.TextFrame2.MarginTop = 1
    $shape.TextFrame2.MarginBottom = 1
    return $shape
}

function Add-Box($slide, [float]$x, [float]$y, [float]$w, [float]$h, $fill, [string]$title, [string]$body='', $accent=$teal, [float]$titleSize=15, [float]$bodySize=10.5) {
    $s = $slide.Shapes.AddShape($msoShapeRoundedRectangle, $x, $y, $w, $h)
    $s.Fill.ForeColor.RGB = $fill
    $s.Line.ForeColor.RGB = $line
    $s.Line.Weight = 1.2
    Add-Text $slide $title ($x+10) ($y+8) ($w-20) 24 $titleSize $accent $true
    if ($body) { Add-Text $slide $body ($x+10) ($y+35) ($w-20) ($h-42) $bodySize $white $false }
    return $s
}

function Add-Header($slide, [string]$eyebrow, [string]$title, [string]$sub='') {
    Add-Text $slide $eyebrow.ToUpper() 42 22 650 18 9 $teal $true
    Add-Text $slide $title 42 42 830 44 26 $white $true
    if ($sub) { Add-Text $slide $sub 42 88 850 26 11 $muted $false }
    $bar = $slide.Shapes.AddShape($msoShapeRectangle, 42, 122, 78, 4)
    $bar.Fill.ForeColor.RGB = $teal; $bar.Line.Visible = $msoFalse
}

function Add-Footer($slide, [int]$n, [string]$label='AI Content Creator') {
    Add-Text $slide $label 42 505 420 14 8 $muted $false
    Add-Text $slide ("{0:00}" -f $n) 890 505 28 14 8 $muted $false $ppAlignRight
}

function Add-Notes($slide, [string]$notes) {
    try {
        $body = $slide.NotesPage.Shapes.Placeholders.Item(2)
        $body.TextFrame.TextRange.Text = $notes
    } catch { }
}

function Add-Arrow($slide, [float]$x1, [float]$y1, [float]$x2, [float]$y2, $color=$teal) {
    $a = $slide.Shapes.AddLine($x1, $y1, $x2, $y2)
    $a.Line.ForeColor.RGB = $color; $a.Line.Weight = 2; $a.Line.EndArrowheadStyle = $msoArrowheadTriangle
    return $a
}

$ppt = New-Object -ComObject PowerPoint.Application
$ppt.Visible = $msoFalse
$pres = $ppt.Presentations.Add()
$pres.PageSetup.SlideWidth = 960
$pres.PageSetup.SlideHeight = 540

function New-Slide([string]$eyebrow, [string]$title, [string]$sub='') {
    $slide = $pres.Slides.Add($pres.Slides.Count + 1, $ppLayoutBlank)
    $bg = $slide.Shapes.AddShape($msoShapeRectangle, 0, 0, 960, 540)
    $bg.Fill.ForeColor.RGB = $navy; $bg.Line.Visible = $msoFalse
    Add-Header $slide $eyebrow $title $sub
    return $slide
}

# 1
$s = $pres.Slides.Add(1, $ppLayoutBlank)
$bg = $s.Shapes.AddShape($msoShapeRectangle,0,0,960,540); $bg.Fill.ForeColor.RGB=$navy; $bg.Line.Visible=$msoFalse
$orb = $s.Shapes.AddShape($msoShapeOval, 655, -55, 355, 355); $orb.Fill.ForeColor.RGB=$panel2; $orb.Fill.Transparency=18; $orb.Line.Visible=$msoFalse
$orb2 = $s.Shapes.AddShape($msoShapeOval, 735, 18, 160, 160); $orb2.Fill.ForeColor.RGB=$teal; $orb2.Fill.Transparency=12; $orb2.Line.Visible=$msoFalse
Add-Text $s 'AI CONTENT CREATOR' 58 58 500 20 11 $teal $true
Add-Text $s 'Intelligent,\nBrand-Aware\nContent Generation' 58 112 640 175 35 $white $true
Add-Text $s 'A grounded Patagonia Content Studio prototype\nthat turns a campaign brief into reviewable, channel-native drafts.' 62 316 560 55 15 $muted
Add-Text $s 'Python - Streamlit - Markdown knowledge bases - OpenAI API' 62 420 620 24 11 $amber $true
Add-Text $s '22-23 October 2026  |  Final project presentation' 62 466 500 18 9 $muted
Add-Notes $s 'Presenter: Martha (opening). Frame this as a working educational prototype, not an automated publishing system. The product identity is Patagonia Content Studio; the presentation title is AI Content Creator - Intelligent, Brand-Aware Content Generation. Preview the promise: grounded, reviewable, channel-specific content.'

# 2
$s = New-Slide '01 / Product' 'The product is a controlled path from brief to publishable draft' 'The system is an intelligent interface between a marketing team and its prospective customers.'
Add-Box $s 52 170 210 150 $panel '1. Brief' 'A human enters the campaign goal, audience and channel.' $teal
Add-Box $s 275 170 210 150 $panel '2. Ground' 'Curated primary + secondary Markdown sources are assembled deterministically.' $blue
Add-Box $s 498 170 210 150 $panel '3. Draft' 'OpenAI generates a channel-specific draft with reviewer notes.' $amber
Add-Box $s 721 170 185 150 $panel '4. Review' 'Edit, revise, approve and export - only after human action.' $coral
Add-Arrow $s 263 245 273 245; Add-Arrow $s 486 245 496 245; Add-Arrow $s 709 245 719 245
Add-Text $s 'What is deliberately out of scope' 52 371 240 18 11 $coral $true
Add-Text $s 'No automated publishing - no auth/database/scheduling - no unsupported facts, prices, discounts or availability' 52 400 810 28 13 $muted
Add-Footer $s 2
Add-Notes $s 'Presenter: Martha. Explain the four-state workflow. Emphasize that approval and export are human-controlled. The excluded scope comes from project_structure.md: no automated social publishing, auth, database or scheduling; no live prices, discounts, availability or unsupported performance claims.'

# 3
$s = New-Slide '02 / Why now' 'The problem is not -can AI write?- - it is -can a brand stay itself?-' 'Generic AI-Slop creates copy that is smooth, interchangeable and weakly accountable.'
Add-Box $s 55 165 250 205 $panel 'Generic AI-Slop' '- Broad slogans\n- Homogenized tone\n- Unclear source of truth\n- Unsupported claims hide in fluent copy' $coral
Add-Box $s 355 165 250 205 $panel 'Business cost' '- Weak differentiation\n- Inconsistent brand identity\n- More reviewer rework\n- Slower path from idea to approved copy' $amber
Add-Box $s 655 165 250 205 $panel 'Design response' '- Two curated knowledge bases\n- Prompt-level grounding rules\n- Channel-native templates\n- Human review as a hard gate' $teal
Add-Text $s 'The target state: distinctive because it is specific, useful and traceable - not because it is -creative- in the abstract.' 75 410 800 35 16 $white $true $ppAlignCenter
Add-Footer $s 3
Add-Notes $s 'Presenter: Martha. Define AI-Slop using the project-s evaluation language: generic phrases, broad promotional language and no required Patagonia context. Then connect each observed failure to a concrete design response. Avoid claiming audience or revenue impact; those were not measured.'

# 4
$s = New-Slide '03 / Strategy' 'A small, explicit operating model keeps the prototype honest' 'Quality, Time and Cost are treated as constraints - not afterthoughts.'
Add-Box $s 52 155 270 155 $panel 'QUALITY' 'Grounded in verified source notes\nDistinct channel tone\nClaim traceability\nObvious UI states' $teal
Add-Box $s 345 155 270 155 $panel 'TIME' 'Two-day end-to-end demo\nAt most two active cards\nPair/review work protects flow\nDay 2 demo path first' $blue
Add-Box $s 638 155 270 155 $panel 'COST' 'Configurable model\nBound generation/revision calls\nUsage captured when available\nAgreed team budget: USD 5' $amber
Add-Text $s 'Stakeholders' 52 350 120 18 11 $teal $true
Add-Text $s 'Sergii - technical lead    Sandra - primary KB owner    Martha - evaluation/usability reviewer' 52 378 820 22 13 $white
Add-Text $s 'Top risk: unsupported or stale claims  -  source-grounding + peer review + approval gate' 52 430 830 24 14 $coral $true
Add-Footer $s 4
Add-Notes $s 'Presenter: Sergii. Cover the quality/time/cost triangle from project_structure.md. Clarify that USD 5 is an agreed budget, not an enforced billing cap. Name documented stakeholders only: Sergii, Sandra, Martha, plus the hypothetical Patagonia approver and course instructor. Call out unsupported or stale claims as the highest-impact risk.'

# 5
$s = New-Slide '04 / Delivery' 'The WBS maps directly to the Kanban path' 'Planning closure precedes development; the team protects a two-card WIP limit.'
$cols = @('PLAN','KNOWLEDGE','GENERATION','INTERFACE + EVAL','DELIVERY')
$items = @('1.1 Board alignment','2.1 Primary KB\n2.2 Secondary KB','3.1 Ingestion\n3.2 Context + RAG\n4.1 OpenAI\n4.2 Templates\n4.3 Pipeline','5.1 Streamlit\n5.2 Uniqueness','6.1 Runtime check\n6.2 Docs + demo')
for ($i=0; $i -lt 5; $i++) {
  $x = 46 + ($i*180)
  Add-Box $s $x 160 160 220 $panel $cols[$i] $items[$i] (@($teal,$blue,$amber,$coral,$green)[$i]) 12 10
  if ($i -lt 4) { Add-Arrow $s ($x+163) 270 ($x+176) 270 $muted }
}
Add-Text $s 'Board rule' 52 414 95 18 11 $teal $true
Add-Text $s 'Maximum two active cards team-wide; every card needs an owner, reviewer, Must ID and verification evidence.' 150 412 740 24 14 $white
Add-Footer $s 5
Add-Notes $s 'Presenter: Sergii. Walk left-to-right through the WBS. The project_structure.md dependency rule is important: planning closure before 2.x-6.x development cards. Link it to Kanban discipline: maximum two active cards, owner/reviewer pairs and evidence captured on the card.'

# 6
$s = New-Slide '05 / Knowledge' 'Two knowledge bases separate authority from context' 'The distinction prevents competitor or trend material from becoming an accidental Patagonia fact.'
Add-Box $s 52 162 340 230 $panel 'PRIMARY / PATAGONIA EVIDENCE' '4 Markdown documents\n\nBrand voice observations\nPublished examples\nProduct facts - style 84212\nCare, repair and reuse\n\nAuthority for Patagonia claims' $teal 14 11
Add-Box $s 568 162 340 230 $panel 'SECONDARY / INDUSTRY CONTEXT' '2 Markdown documents\n\nCompetitor context\nOutdoor participation + textile reuse\n\nPositioning input only\nNever transfer competitor features or claims to Patagonia' $blue 14 11
Add-Arrow $s 395 277 565 277 $amber
Add-Text $s 'Markdown - parser - metadata + sections - deterministic context bundle - prompt' 128 427 700 26 15 $white $true $ppAlignCenter
Add-Footer $s 6
Add-Notes $s 'Presenter: Sandra. Explain the source separation. The loader ingests four primary and two secondary documents, preserves metadata and heading-level sections, then the context assembler serializes separate strings. The secondary corpus informs positioning only; it is never a source for Patagonia product facts.'

# 7
$s = New-Slide '06 / Architecture decision' 'RAG was consciously deferred - and measured conditions are defined' 'Current implementation: fixed, deterministic context injection. No query-based retrieval, embeddings or vector store.'
Add-Box $s 52 158 255 230 $panel 'WHY THIS FITS NOW' 'Small, stable corpus\nReviewable baseline\nTwo-day schedule\nBounded source inclusion\nSimple failure modes' $teal 14 11
Add-Box $s 352 158 255 230 $panel 'WHAT IS IMPLEMENTED' 'Loads 6 curated Markdown files\nSerializes primary + secondary contexts\n14,474 serialized characters\n40,000-character guardrail\nOne smoke-test request: 4,230 tokens' $blue 14 11
Add-Box $s 652 158 255 230 $panel 'WHEN TO REVISIT' 'Corpus grows or overlaps\nFrequent updates\nMore diverse briefs\nMeasured token/latency burden\nReview burden makes fixed inclusion inefficient' $amber 14 11
Add-Text $s 'RAG is not -better by default-; it becomes justified by measured corpus size, request diversity, update frequency and context limits.' 82 425 790 28 15 $white $true $ppAlignCenter
Add-Footer $s 7
Add-Notes $s 'Presenter: Sergii. Defend the RAG choice with the actual decision record. Mention the one Day 1 smoke test measurements as indicative only: 14,474 serialized context characters, 3,683 input tokens, 547 output tokens, 4,230 total, 6.35 seconds. Do not call this a benchmark or production fit proof.'

# 8
$s = New-Slide '07 / Technical flow' 'From Markdown sources to a reviewable draft' 'The pipeline is intentionally inspectable at each boundary.'
$steps = @(
  @('INGEST','document_processor.py','Parse Markdown; validate metadata; preserve sections'),
  @('ASSEMBLE','knowledge_base.py','Build deterministic primary + secondary context'),
  @('PROMPT','prompt_templates.py','Apply grounding, channel constraints and anti-slop rules'),
  @('GENERATE','llm_integration.py','Call configurable OpenAI model; capture usage metadata'),
  @('REVIEW','content_pipeline.py','Feedback, revision, edit, approval and export')
)
for ($i=0; $i -lt $steps.Count; $i++) {
  $x = 45 + ($i*180)
  Add-Box $s $x 175 160 170 $panel $steps[$i][0] ($steps[$i][1] + "`n" + $steps[$i][2]) (@($teal,$blue,$amber,$coral,$green)[$i]) 13 9.5
  if ($i -lt 4) { Add-Arrow $s ($x+162) 260 ($x+178) 260 $muted }
}
Add-Text $s 'Human gate' 52 400 100 18 11 $coral $true
Add-Text $s 'The draft cannot become approved/exported content without an explicit human confirmation of the exact revision.' 160 398 720 28 14 $white
Add-Footer $s 8
Add-Notes $s 'Presenter: Sergii. Map each box to the repository files. The pipeline returns reviewer notes and source traces alongside channel copy. The human gate is enforced in content_pipeline.py and the Streamlit/CLI paths; approval must be explicit and the current revision must match.'

# 9
$s = New-Slide '08 / Demonstration' 'The working application demo follows one visible state machine' 'Demo path: load campaign - generate - revise/edit - approve - export.'
Add-Box $s 52 158 190 245 $panel 'CAMPAIGN' 'Channel selector\nBrief text area\nLoad campaign\n\nImplemented in app.py' $teal 14 11
Add-Box $s 267 158 190 245 $panel 'DRAFT' 'Generate draft\nChannel copy\nReviewer notes\nResponse metadata\n\nOpenAI response surfaced' $blue 14 11
Add-Box $s 482 158 190 245 $panel 'REVIEW' 'Feedback for revision\nManual edit\nSave edit\nApproval checkbox\n\nDirty edits block approval' $amber 14 11
Add-Box $s 697 158 210 245 $panel 'EXPORT' 'Approve exact revision\nDownload Markdown\nDownload JSON metadata\n\nHuman action required' $coral 14 11
Add-Arrow $s 243 280 263 280; Add-Arrow $s 458 280 478 280; Add-Arrow $s 673 280 693 280
Add-Text $s 'Evidence status: functionality is implemented and manually verified for Instagram; LinkedIn/email live checks remain pending. No application screenshot is present in the repository.' 55 435 850 28 12 $muted $false $ppAlignCenter
Add-Footer $s 9
Add-Notes $s 'Presenter: Martha. Demonstrate the actual Streamlit app if available: load an Instagram campaign, generate, show reviewer notes, make a manual edit or request revision, confirm approval, and show downloads. The repository instructions say Instagram generation/revision/manual editing/approval/export and light/dark switching were manually verified; LinkedIn/email live checks remain pending. Be explicit that this slide is an editable walkthrough, not a fabricated screenshot.'

# 10
$s = New-Slide '09 / Uniqueness' 'The evaluation shows why context beats generic fluency' 'The evidence is a first-pass fixture comparison, not a claim about live model performance.'
Add-Box $s 55 165 355 220 $panel 'GENERIC FIXTURE - FAILED' '-Elevate your everyday adventure with a game-changer.-\n\nNo Patagonia context\nFlags: -elevate your- + -game-changer-' $coral 15 12
Add-Box $s 550 165 355 220 $panel 'CONTEXTUAL FIXTURE - PASSED' 'Names the Nano Puff jacket\nConnects to a changing forecast\nIncludes repair + reuse guidance\nNo flagged generic phrases' $teal 15 12
Add-Text $s 'Differentiation contract' 55 418 160 18 11 $amber $true
Add-Text $s 'Specificity  -  Productive tension  -  Channel-native writing  -  Anti-slop control' 225 416 650 22 14 $white
Add-Footer $s 10
Add-Notes $s 'Presenter: Martha. Use the documented uniqueness-evaluation.md result. The generic fixture failed observable checks; the contextual fixture passed required context terms and avoided the flagged phrases. Clarify that the smoke test uses an offline fixture with live_api_call false, so this is an integration/review-aid result, not a live model benchmark.'

# 11
$s = New-Slide '10 / Prompting' 'Advanced prompting turns brand intent into testable constraints' 'The system does not ask the model to -be creative-; it specifies what good looks like and what must not happen.'
Add-Box $s 52 158 270 235 $panel 'GROUNDING' 'Primary is authoritative\nSecondary is positioning only\nSeparate facts from interpretation\nPreserve limitations and dates' $teal 14 11
Add-Box $s 345 158 270 235 $panel 'CHANNEL SHAPE' 'Instagram: 60-120 words\nLinkedIn: 120-200 words\nEmail: subject/preheader/body limits\nOne CTA; format-native rhythm' $blue 14 11
Add-Box $s 638 158 270 235 $panel 'ANTI-SLOP' 'Avoid cliches and superlatives\nNo vague sustainability claims\nNo invented facts\nReturn copy + reviewer notes' $coral 14 11
Add-Text $s 'Prompt output is inspectable: exact sections, source paths/URLs, facts used, interpretations and unresolved limitations.' 80 425 800 26 14 $white $true $ppAlignCenter
Add-Footer $s 11
Add-Notes $s 'Presenter: Sandra. Explain the prompt strategy as a quality system. Templates enforce channel-specific shape, the grounding rules restrict claims, and reviewer notes make the reasoning auditable. Mention the water-resistant versus waterproof distinction as an example of a concrete claim-safety rule.'

# 12
$s = New-Slide '11 / Implementation' 'The technical spine is small enough to inspect end-to-end' 'Repository structure, configuration and AGENTS.md are part of the product discipline.'
Add-Box $s 52 155 255 255 $panel 'DOCUMENT PROCESSING' 'src/document_processor.py\nMarkdownIt parser\nRequired metadata schema\nHeading-path sections\nSource URLs + access dates' $teal 14 10.5
Add-Box $s 352 155 255 255 $panel 'INTEGRATION' 'src/llm_integration.py\nOPENAI_API_KEY\nOPENAI_MODEL\nUsage capture when available\nNo secrets logged' $blue 14 10.5
Add-Box $s 652 155 255 255 $panel 'DELIVERY SURFACE' 'app.py - Streamlit\nsrc/main.py - CLI\ntemplates/*.md\noutputs/ - approved exports\ntests/ - automated checks' $amber 14 10.5
Add-Text $s 'AGENTS.md keeps scope explicit: Must IDs M1-M8, assigned file scope, human approval, no fabricated facts, no staging/committing/pushing without permission.' 60 435 840 28 13 $white $true $ppAlignCenter
Add-Footer $s 12
Add-Notes $s 'Presenter: Sergii. Show the project map and how each Must ID is anchored to files and checks. AGENTS.md is not decorative: it sets the project-s quality bar, protects secrets, requires human approval, limits WIP and prevents scope expansion.'

# 13
$s = New-Slide '12 / Learning' 'The hard parts were control problems, not syntax problems' 'The project-s solutions are mostly boundary decisions: what to include, what to exclude, and how to prove it.'
Add-Box $s 52 158 265 230 $panel 'CHALLENGE' 'Grounding without retrieval\nSmall corpus, mixed authority\nRisk of context leakage' $coral 14 11
Add-Box $s 347 158 265 230 $panel 'SOLUTION' 'Separate primary/secondary\nDeterministic bundle\nMetadata + section traceability\nMeasured revisit conditions' $teal 14 11
Add-Box $s 642 158 265 230 $panel 'LESSON' 'Do not infer RAG need from hype\nDo not call a fixture a benchmark\nHuman review remains part of the system' $amber 14 11
Add-Text $s 'A strong prototype is allowed to say -not measured yet- - as long as it records what would change the decision.' 85 425 790 26 15 $white $true $ppAlignCenter
Add-Footer $s 13
Add-Notes $s 'Presenter: Martha. Cover three lessons: deterministic context is a credible baseline for a small corpus; evidence labels matter (fixture versus live response); and human review is a product feature for trust, not a temporary inconvenience. Mention corpus measurements are not full performance benchmarks.'

# 14
$s = New-Slide '13 / Kanban evidence' 'Day 1 made the work visible; Day 2 turned it into a demo path' 'Actual Day 1 board evidence is preserved in the repository.'
$imgPath = Join-Path $root 'docs\evidence\p2-kanban-day1.png'
if (Test-Path $imgPath) {
    $pic = $s.Shapes.AddPicture($imgPath, $msoFalse, $msoTrue, 55, 150, 485, 300)
    $pic.Line.ForeColor.RGB = $line
}
Add-Box $s 580 155 325 135 $panel 'DAY 1 - VERIFIED' 'Planning, KBs, loader, context injection, templates, offline integration, live Instagram smoke test; 62 offline tests passed.' $teal 14 10.5
Add-Box $s 580 315 325 135 $panel 'DAY 2 - TARGET / STATUS' 'Pipeline, UI, review/export, evaluation, docs and presentation. Instagram UI path is documented as manually verified; LinkedIn/email live checks remain pending.' $amber 14 10.5
Add-Text $s 'Screenshot source: docs/evidence/p2-kanban-day1.png' 55 462 485 18 9 $muted
Add-Footer $s 14
Add-Notes $s 'Presenter: Sandra. Use the actual Day 1 board screenshot. Day 1 status records 62 offline tests passed and a successful live Instagram smoke test; Sergii reviewed the live Instagram draft, but publication approval was not granted. The Day 2 status is bounded by the repository-s own evidence: Instagram workflow manually verified, LinkedIn/email live checks pending.'

# 15
$s = New-Slide '14 / Outcomes' 'What exists now - and what remains deliberately open' 'The outcome is a grounded, reviewable prototype with a clear next decision set.'
Add-Box $s 52 155 260 240 $panel 'IMPLEMENTED' 'Two KBs + metadata\nDeterministic context\nThree channel templates\nOpenAI integration\nCLI + Streamlit flow\nHuman approval/export' $teal 14 10.5
Add-Box $s 350 155 260 240 $panel 'LIMITATIONS' 'No RAG / vector store\nNo automated publishing\nNo auth/database/scheduling\nCost not calculated\nLinkedIn/email live checks pending\nNo production deployment evidence' $coral 14 10.5
Add-Box $s 648 155 260 240 $panel 'NEXT DEVELOPMENT' 'Preserve live generic/contextual outputs\nMeasure repeated-request burden\nRevisit retrieval when evidence says so\nAdd broader runtime validation\nCapture application screenshots\nDeploy only if scope supports it' $amber 14 10.5
Add-Footer $s 15
Add-Notes $s 'Presenter: Martha. Separate implemented capabilities from proposed improvements. The next step is not automatically -add a vector database-; it is to preserve stronger same-model comparisons, measure token/latency/review burden, and revisit architecture if the corpus or request diversity grows.'

# 16
$s = New-Slide '15 / Close' 'Brand-aware generation is a system of evidence, constraints and judgment' 'The differentiator is not a larger promise. It is a more accountable path to useful content.'
Add-Text $s 'BRIEF' 83 180 130 20 11 $teal $true $ppAlignCenter
Add-Text $s '-' 215 178 40 24 18 $muted $true $ppAlignCenter
Add-Text $s 'GROUND' 260 180 130 20 11 $blue $true $ppAlignCenter
Add-Text $s '-' 392 178 40 24 18 $muted $true $ppAlignCenter
Add-Text $s 'DRAFT' 438 180 130 20 11 $amber $true $ppAlignCenter
Add-Text $s '-' 570 178 40 24 18 $muted $true $ppAlignCenter
Add-Text $s 'REVIEW' 615 180 130 20 11 $coral $true $ppAlignCenter
Add-Text $s '-' 747 178 40 24 18 $muted $true $ppAlignCenter
Add-Text $s 'APPROVE' 792 180 90 20 11 $green $true $ppAlignCenter
Add-Text $s 'One clear takeaway' 260 265 440 26 17 $white $true $ppAlignCenter
Add-Text $s 'Specificity + source discipline + channel-native prompting\nmake the output more distinguishable and more reviewable.' 165 305 630 60 21 $teal $true $ppAlignCenter
Add-Text $s 'Thank you' 400 430 160 24 13 $muted $false $ppAlignCenter
Add-Footer $s 16 'AI Content Creator - Patagonia Content Studio'
Add-Notes $s 'Presenters: all three. Martha restates the takeaway. Sandra connects it to brand voice and source discipline. Sergii closes with the implementation and next measurement step. Invite questions about the RAG decision, human approval gate or uniqueness evidence. Do not overclaim publication readiness or model performance.'

$pres.SaveAs($pptxPath, $ppSaveAsOpenXMLPresentation)
try { $pres.ExportAsFixedFormat($pdfPath, $ppFixedFormatTypePDF, $ppFixedFormatIntentScreen) } catch { }
$pres.Close(); $ppt.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($pres) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
Write-Output $pptxPath
if (Test-Path $pdfPath) { Write-Output $pdfPath }
