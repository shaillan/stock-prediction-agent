# -*- coding: utf-8 -*-
"""
Generate LangChain & LangGraph Agent PPT
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

# ===== Colors =====
DARK_BG = RGBColor(0x1A, 0x1A, 0x2E)
ACCENT_BLUE = RGBColor(0x4F, 0x8C, 0xFF)
ACCENT_GREEN = RGBColor(0x00, 0xCF, 0x8A)
ACCENT_ORANGE = RGBColor(0xFF, 0x9F, 0x43)
ACCENT_PURPLE = RGBColor(0xA2, 0x7B, 0xFF)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xB0, 0xBA, 0xD0)
SLIDE_BG = RGBColor(0x16, 0x18, 0x2A)
CARD_BG = RGBColor(0x22, 0x25, 0x3E)
CODE_BG = RGBColor(0x0D, 0x0F, 0x1A)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
TOTAL = 21


def bg(slide, color=SLIDE_BG):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def rect(slide, l, t, w, h, color, stype=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(stype, l, t, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = color
    s.line.fill.background()
    return s


def tb(slide, l, t, w, h, text, fs=18, color=WHITE, bold=False, align=PP_ALIGN.LEFT, font="Microsoft YaHei"):
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(fs)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font
    p.alignment = align
    return box


def line(slide, l, t, w, color=ACCENT_BLUE, h=Pt(3)):
    return rect(slide, l, t, w, h, color)


def card(slide, l, t, w, h, title, items, accent=ACCENT_BLUE):
    rect(slide, l, t, w, h, CARD_BG)
    line(slide, l, t, w, accent, Pt(4))
    tb(slide, l + Inches(0.2), t + Inches(0.15), w - Inches(0.4), Inches(0.4),
       title, fs=16, color=accent, bold=True)
    for j, (text, fs2, c2, b2) in enumerate(items):
        tb(slide, l + Inches(0.25), t + Inches(0.6) + Inches(j * 0.32),
           w - Inches(0.5), Inches(0.35), text, fs=fs2, color=c2, bold=b2)


def new_slide():
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg(s)
    return s


def pn(slide, n):
    tb(slide, Inches(12.2), Inches(7.1), Inches(1), Inches(0.3),
       f"{n}/{TOTAL}", fs=10, color=LIGHT_GRAY, align=PP_ALIGN.RIGHT)


def section(slide, num, title):
    tb(slide, Inches(0.5), Inches(6.8), Inches(3), Inches(0.3),
       f"Part {num}  |  {title}", fs=10, color=ACCENT_BLUE)


def title_content(slide, title, subtitle):
    line(slide, Inches(0.8), Inches(2.6), Inches(1.5), ACCENT_BLUE)
    tb(slide, Inches(0.8), Inches(2.8), Inches(11), Inches(0.8), title, fs=36, color=WHITE, bold=True)
    tb(slide, Inches(0.8), Inches(3.6), Inches(11), Inches(0.5), subtitle, fs=16, color=LIGHT_GRAY)


def flow(slide, l, t, nodes):
    box_w = Inches(1.65)
    box_h = Inches(0.55)
    gap = Inches(0.35)
    x = l
    for i, (name, color) in enumerate(nodes):
        s = rect(slide, x, t, box_w, box_h, color, MSO_SHAPE.ROUNDED_RECTANGLE)
        tf = s.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = name
        p.font.size = Pt(10)
        p.font.color.rgb = WHITE
        p.font.name = "Microsoft YaHei"
        p.alignment = PP_ALIGN.CENTER
        if i < len(nodes) - 1:
            a = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x + box_w, t + Inches(0.17), gap, Inches(0.2))
            a.fill.solid()
            a.fill.fore_color.rgb = ACCENT_BLUE
            a.line.fill.background()
        x += box_w + gap


# ================================================================
# SLIDE 1: Cover
# ================================================================
s = new_slide()
rect(s, Inches(0), Inches(0), prs.slide_width, Inches(3.5), RGBColor(0x0F, 0x11, 0x22))
line(s, Inches(1), Inches(3.2), Inches(3), ACCENT_BLUE, Pt(6))
tb(s, Inches(1), Inches(1.5), Inches(11), Inches(1), "LangChain & LangGraph", fs=48, color=WHITE, bold=True)
tb(s, Inches(1), Inches(2.3), Inches(11), Inches(0.6), "Agent Building - From Concepts to Practice", fs=36, color=ACCENT_BLUE, bold=True)
tb(s, Inches(1), Inches(4.5), Inches(11), Inches(0.5), "From Core Concepts to Stock Prediction Agent Full Pipeline", fs=18, color=LIGHT_GRAY)
tb(s, Inches(1), Inches(5.5), Inches(11), Inches(0.4),
   "July 2026  |  Based on Real A-Share Data  |  LLM-Driven Multi-Source Analysis", fs=14, color=LIGHT_GRAY)
tags = ["StateGraph", "TypedDict", "Conditional Edges", "Prompt Engineering", "Streamlit"]
for i, tag in enumerate(tags):
    x = Inches(1 + i * 2.4)
    shape = rect(s, x, Inches(6.2), Inches(2.1), Inches(0.45), CARD_BG, MSO_SHAPE.ROUNDED_RECTANGLE)
    tf = shape.text_frame
    p = tf.paragraphs[0]
    p.text = tag
    p.font.size = Pt(11)
    p.font.color.rgb = ACCENT_BLUE
    p.font.name = "Microsoft YaHei"
    p.alignment = PP_ALIGN.CENTER

# ================================================================
# SLIDE 2: TOC
# ================================================================
s = new_slide()
title_content(s, "Contents", "Agenda")
sections = [
    ("01", "LangChain & LangGraph Overview", "Why do we need an agent orchestration framework?"),
    ("02", "LangGraph Core Concepts", "StateGraph / State / Nodes / Edges / Routing"),
    ("03", "Real Project: Stock Prediction Agent", "5-Node Pipeline + LLM Multi-Source Analysis"),
    ("04", "Key Techniques & Lessons Learned", "Prompt Engineering / Error Handling / Serialization Tricks"),
]
for i, (num, ttl, desc) in enumerate(sections):
    y = Inches(3.8) + Inches(i * 0.85)
    tb(s, Inches(1), y, Inches(0.6), Inches(0.5), num, fs=28, color=ACCENT_BLUE, bold=True)
    line(s, Inches(1.7), y + Inches(0.05), Pt(3), ACCENT_BLUE, Inches(0.4))
    tb(s, Inches(2), y, Inches(9), Inches(0.4), ttl, fs=20, color=WHITE, bold=True)
    tb(s, Inches(2), y + Inches(0.35), Inches(9), Inches(0.35), desc, fs=13, color=LIGHT_GRAY)
pn(s, 1)

# ================================================================
# SLIDE 3: What is LangChain
# ================================================================
s = new_slide()
section(s, 1, "LangChain & LangGraph Overview")
title_content(s, "What is LangChain?", "LLM Application Framework - Connecting Models, Tools & Data")

c1 = [("Chains: Chain multiple LLM calls", 13, WHITE, False),
      ("Agents: LLM autonomously chooses tools", 13, WHITE, False),
      ("Tools: Encapsulate APIs / databases", 13, WHITE, False),
      ("Memory: Conversation history management", 13, WHITE, False)]
c2 = [("Chat Models: Unified LLM call interface", 13, WHITE, False),
      ("Prompts: Templated prompt management", 13, WHITE, False),
      ("Retrievers: Document search & RAG", 13, WHITE, False),
      ("Callbacks: Logging & monitoring", 13, WHITE, False)]
c3 = [("Unify different LLM provider APIs", 13, WHITE, False),
      ("Manage complex multi-step reasoning", 13, WHITE, False),
      ("Connect LLM with external data sources", 13, WHITE, False),
      ("Reuse common application patterns", 13, WHITE, False)]
card(s, Inches(0.8), Inches(4.0), Inches(3.7), Inches(2.6), "Core Capabilities", c1, ACCENT_BLUE)
card(s, Inches(4.8), Inches(4.0), Inches(3.7), Inches(2.6), "Core Components", c2, ACCENT_GREEN)
card(s, Inches(8.8), Inches(4.0), Inches(3.7), Inches(2.6), "Problems Solved", c3, ACCENT_ORANGE)
pn(s, 2)

# ================================================================
# SLIDE 4: What is LangGraph
# ================================================================
s = new_slide()
section(s, 1, "LangChain & LangGraph Overview")
title_content(s, "What is LangGraph?", "Stateful, Graph-Based Multi-Agent Orchestration Framework")

c1 = [("LangChain: Chain is a 'line', nodes execute sequentially", 14, WHITE, False),
      ("LangGraph: Graph branches, loops, conditions", 14, ACCENT_GREEN, True),
      ("", 8, WHITE, False),
      ("LangGraph = Part of the LangChain ecosystem", 13, LIGHT_GRAY, False),
      ("Dedicated to complex Agent orchestration/scheduling", 13, LIGHT_GRAY, False),
      ("Still uses LangChain's LLM/Tool/Prompt underneath", 13, LIGHT_GRAY, False)]
c2 = [("Conditional Routing: Dynamically choose next node by State", 14, WHITE, False),
      ("Loop Support: Agent can iteratively think & call tools", 14, WHITE, False),
      ("State Persistence: Shared TypedDict State across all nodes", 14, WHITE, False),
      ("Observability: Built-in Checkpoint & graph visualization", 14, WHITE, False),
      ("Streaming: stream() method for real-time output", 14, WHITE, False)]
card(s, Inches(0.8), Inches(3.9), Inches(5.8), Inches(3.2), "LangChain vs LangGraph", c1, ACCENT_BLUE)
card(s, Inches(7.0), Inches(3.9), Inches(5.8), Inches(3.2), "LangGraph Key Features", c2, ACCENT_GREEN)
pn(s, 3)

# ================================================================
# SLIDE 5: StateGraph
# ================================================================
s = new_slide()
section(s, 2, "LangGraph Core Concepts")
title_content(s, "StateGraph - The Stateful Graph Engine",
              "The entire Agent workflow is defined as a 'graph': Nodes + Edges + State")

nds = [("STATE\n{score, decision}", RGBColor(0x3D, 0x3D, 0x6B)),
       ("evaluate\nNode", ACCENT_BLUE), ("route\nRouter", ACCENT_ORANGE),
       ("high\nNode", ACCENT_GREEN), ("medium\nNode", ACCENT_GREEN), ("low\nNode", ACCENT_GREEN)]
flow(s, Inches(0.8), Inches(4.2), [(n, c) for n, c in nds])
tb(s, Inches(0.8), Inches(5.2), Inches(11), Inches(0.4),
   "State flows through all nodes, each node returns partial updates, Graph auto-merges", fs=13, color=LIGHT_GRAY)

for i, (ttl, desc) in enumerate([
    ("State", "TypedDict-defined schema\nFlows through all nodes, auto-merge"),
    ("Nodes", "Python functions, receive State\nReturn partial State update as dict"),
    ("Edges", "Define connections between nodes\nNormal edges / Conditional edges"),
]):
    x = Inches(0.8 + i * 4.1)
    parts = desc.split("\n")
    card(s, x, Inches(5.7), Inches(3.7), Inches(1.3), ttl,
         [(parts[0], 12, WHITE, False), (parts[1], 12, LIGHT_GRAY, False)], ACCENT_BLUE)
pn(s, 4)

# ================================================================
# SLIDE 6: State
# ================================================================
s = new_slide()
section(s, 2, "LangGraph Core Concepts")
title_content(s, "State - Define Shared State with TypedDict",
              "State is the 'memory' of the graph - all nodes follow this schema")

code = (
    "class AgentState(TypedDict, total=False):\n"
    "    # ===== Input =====\n"
    "    stock_code: str\n"
    "    stock_name: str\n"
    "    start_date: str\n"
    "    end_date: str\n"
    "    # ===== Data Outputs =====\n"
    "    kline_data: Optional[Any]     # pd.DataFrame\n"
    "    realtime_quote: Optional[Dict]\n"
    "    financial_data: Optional[Dict]\n"
    "    news_data: Optional[List[Dict]]\n"
    "    # ===== Analysis Results =====\n"
    "    technical_analysis_result: Optional[str]\n"
    "    prediction: Optional[Dict]     # JSON\n"
    "    final_report: Optional[str]    # Markdown\n"
    "    # ===== Control =====\n"
    "    status: str\n"
    "    errors: List[str]\n"
    "    messages: Annotated[list, add_messages]\n"
    "    # ===== LLM Config =====\n"
    "    llm_model: str\n"
    "    llm_api_key: str\n"
    "    llm_base_url: str"
)
cs = rect(s, Inches(0.8), Inches(3.9), Inches(6.0), Inches(3.3), CODE_BG)
tf = cs.text_frame; tf.word_wrap = True
tf.paragraphs[0].text = code
tf.paragraphs[0].font.size = Pt(8.5)
tf.paragraphs[0].font.color.rgb = ACCENT_GREEN
tf.paragraphs[0].font.name = "Cascadia Code"

c1 = [("Python type-hint syntax", 14, WHITE, False),
      ("total=False -> all fields optional", 13, LIGHT_GRAY, False),
      ("Each node only returns its own fields", 13, LIGHT_GRAY, False)]
c2 = [("1. Organize fields by phase", 13, WHITE, False),
      ("2. Separate control fields (status/errors)", 13, WHITE, False),
      ("3. Optional fields default to None", 13, WHITE, False),
      ("4. total=False avoids init all fields", 13, LIGHT_GRAY, False)]
card(s, Inches(7.2), Inches(3.9), Inches(5.5), Inches(1.4), "TypedDict", c1, ACCENT_BLUE)
card(s, Inches(7.2), Inches(5.6), Inches(5.5), Inches(1.4), "Key Design Principles", c2, ACCENT_ORANGE)
pn(s, 5)

# ================================================================
# SLIDE 7: Nodes
# ================================================================
s = new_slide()
section(s, 2, "LangGraph Core Concepts")
title_content(s, "Nodes - Node Functions",
              "Each node is a Python function: receives entire State -> returns partial update dict")

code = (
    "def data_collection_node(state: AgentState) -> dict:\n"
    '    """Data collection node"""\n'
    '    stock_code = state["stock_code"]  # read input\n'
    "\n"
    "    # ... call AKShare to fetch data ...\n"
    '    kline_df = client.get_stock_kline(stock_code)\n'
    "\n"
    "    return {                         # partial update\n"
    '        "status": "collecting",\n'
    '        "kline_data": kline_df,      # auto-merge into State\n'
    '        "errors": [],\n'
    "    }"
)
cs = rect(s, Inches(0.8), Inches(3.9), Inches(6.0), Inches(2.3), CODE_BG)
tf = cs.text_frame; tf.word_wrap = True
tf.paragraphs[0].text = code
tf.paragraphs[0].font.size = Pt(10)
tf.paragraphs[0].font.color.rgb = ACCENT_GREEN
tf.paragraphs[0].font.name = "Cascadia Code"

c1 = [("Input: full State (TypedDict)", 14, WHITE, False),
      ("Output: dict (only fields updated by this node)", 14, ACCENT_GREEN, True),
      ("Framework auto-merges back to State", 14, LIGHT_GRAY, False),
      ("", 8, WHITE, False),
      ("Same keys overwrite", 13, ACCENT_ORANGE, False),
      ("Unreturned fields keep original values", 13, LIGHT_GRAY, False),
      ("Immutable: do NOT mutate state, return new dict", 13, LIGHT_GRAY, False),
      ("", 8, WHITE, False),
      ("Supports async def for async nodes", 13, ACCENT_PURPLE, False)]
card(s, Inches(7.2), Inches(3.9), Inches(5.5), Inches(3.0), "Node Function Rules", c1, ACCENT_BLUE)
pn(s, 6)

# ================================================================
# SLIDE 8: Edges
# ================================================================
s = new_slide()
section(s, 2, "LangGraph Core Concepts")
title_content(s, "Edges - Normal Edges vs Conditional Edges",
              "Determining 'which node goes next' - the core of Agent intelligent decision-making")

c1 = [("Fixed flow: A -> B -> C", 14, WHITE, False),
      ('graph.add_edge("evaluate", "high")', 12, ACCENT_GREEN, False),
      ("", 8, WHITE, False),
      ("Use cases:", 13, ACCENT_ORANGE, True),
      ("  Linear pipeline, each node's next step is fixed", 12, LIGHT_GRAY, False),
      ("  e.g.: Data -> Analysis -> Prediction -> Report", 12, LIGHT_GRAY, False)]
c2 = [("Dynamic routing: choose next node by State value", 14, ACCENT_ORANGE, True),
      ("graph.add_conditional_edges(", 12, ACCENT_GREEN, False),
      ('    "evaluate", route_fn,  # routing function', 12, ACCENT_GREEN, False),
      ('    {"high":"high", "medium":"medium", ...})', 12, ACCENT_GREEN, False),
      ("", 8, WHITE, False),
      ("Use cases:", 13, ACCENT_ORANGE, True),
      ("  Branch by score/sentiment/status", 12, LIGHT_GRAY, False),
      ("  Agent decides which tool to call next", 12, LIGHT_GRAY, False)]
card(s, Inches(0.8), Inches(3.9), Inches(5.8), Inches(3.2), "Normal Edge (add_edge)", c1, ACCENT_BLUE)
card(s, Inches(7.0), Inches(3.9), Inches(5.8), Inches(3.2), "Conditional Edge (add_conditional_edges)", c2, ACCENT_ORANGE)

tb(s, Inches(0.8), Inches(6.8), Inches(11), Inches(0.4),
   'def route_by_score(state) -> Literal["high","medium","low"]: return "high" if state["score"]>0.8 else ("medium" if state["score"]>0.5 else "low")',
   fs=11, color=ACCENT_GREEN)
pn(s, 7)

# ================================================================
# SLIDE 9: START/END + compile + invoke
# ================================================================
s = new_slide()
section(s, 2, "LangGraph Core Concepts")
title_content(s, "START / END / compile / invoke",
              "Build + Compile + Execute - LangGraph's Three-Step Workflow")

steps = [
    ("1. Build Graph", ACCENT_BLUE,
     ["workflow = StateGraph(State)", "workflow.add_node(...)",
      "workflow.add_edge(...)", "workflow.set_entry_point(...)"]),
    ("2. Compile Graph", ACCENT_GREEN,
     ["app = workflow.compile()", "-> Validates graph integrity",
      "-> Binds Checkpoint", "-> Returns executable CompiledGraph"]),
    ("3. Execute Graph", ACCENT_ORANGE,
     ['result = app.invoke(initial_state)', "-> Pass complete initial State",
      "-> Execute nodes in edge order", "-> Return final State"]),
    ("4. Stream (Optional)", ACCENT_PURPLE,
     ["for chunk in app.stream(state):", "    print(chunk)  # per-node output",
      "-> Suitable for UI real-time updates", ""]),
]
for i, (ttl, color, lines) in enumerate(steps):
    x = Inches(0.8 + i * 3.15)
    body = [(l, 11, WHITE if j == 0 else LIGHT_GRAY, j == 0) for j, l in enumerate(lines)]
    card(s, x, Inches(3.9), Inches(2.85), Inches(2.4), ttl, body, color)

tb(s, Inches(0.8), Inches(6.8), Inches(11), Inches(0.4),
   "invoke() requires a COMPLETE initial State - all non-Optional fields must have values, otherwise KeyError",
   fs=13, color=ACCENT_ORANGE)
pn(s, 8)

# ================================================================
# SLIDE 10: Graph Visualization
# ================================================================
s = new_slide()
section(s, 2, "LangGraph Core Concepts")
title_content(s, "Graph Visualization - Debug Tool",
              "Use draw_mermaid() or draw_png() to visually see the entire Agent structure")

mermaid = (
    "graph TD;\n"
    "    __start__ --> evaluate;\n"
    "    evaluate -.-> high;\n"
    "    evaluate -.-> medium;\n"
    "    evaluate -.-> low;\n"
    "    high --> __end__;\n"
    "    medium --> __end__;\n"
    "    low --> __end__;"
)
cs = rect(s, Inches(0.8), Inches(3.9), Inches(5.8), Inches(1.6), CODE_BG)
tf = cs.text_frame; tf.word_wrap = True
tf.paragraphs[0].text = mermaid
tf.paragraphs[0].font.size = Pt(11)
tf.paragraphs[0].font.color.rgb = ACCENT_GREEN
tf.paragraphs[0].font.name = "Cascadia Code"

c1 = [("draw_mermaid(): Generate Mermaid text -> render in Jupyter", 12, WHITE, False),
      ("draw_png(): Generate PNG image -> needs pygraphviz + graphviz", 12, WHITE, False),
      ("Windows issue: pygraphviz needs extra Graphviz system install", 12, ACCENT_ORANGE, False),
      ("Solution: pip install graphviz, or use Mermaid instead", 12, ACCENT_GREEN, False)]
c2 = [("Always display_graph() during development", 14, WHITE, False),
      ("Check node count + edge count matches expectation", 14, WHITE, False),
      ("Conditional edges shown as dotted (-.->), normal as solid (-->)", 14, LIGHT_GRAY, False),
      ("", 8, WHITE, False),
      ("xray=True parameter:", 13, ACCENT_BLUE, True),
      ("Shows input/output State fields for each node", 13, LIGHT_GRAY, False),
      ("Helps locate State field mismatch issues", 13, LIGHT_GRAY, False)]
card(s, Inches(0.8), Inches(5.7), Inches(5.8), Inches(1.5), "Rendering Methods", c1, ACCENT_BLUE)
card(s, Inches(7.0), Inches(3.9), Inches(5.8), Inches(3.3), "Practical Tips", c2, ACCENT_GREEN)
pn(s, 9)

# ================================================================
# SLIDE 11: Project Overview
# ================================================================
s = new_slide()
section(s, 3, "Real Project: Stock Prediction Agent")
title_content(s, "Project Architecture Overview",
              "LangGraph 5-Node Linear Pipeline + Streamlit Frontend + AKShare Data Source")

nds = [("1. Data Collection\nAKShare + Concurrent", ACCENT_BLUE),
       ("2. Technical Analysis\nIndicators + LLM", ACCENT_GREEN),
       ("3. News Sentiment\nLLM Analysis", ACCENT_ORANGE),
       ("4. Prediction\nMulti-Source Fusion", ACCENT_PURPLE),
       ("5. Report Gen\nMarkdown", RGBColor(0xE0, 0x55, 0x8B))]
flow(s, Inches(0.5), Inches(3.8), [(n, c) for n, c in nds])

c1 = [("LangGraph: Agent workflow orchestration", 13, WHITE, False),
      ("LangChain: Unified LLM calling", 13, WHITE, False),
      ("AKShare: A-share data source", 13, WHITE, False),
      ("Plotly: K-line chart visualization", 13, WHITE, False),
      ("Streamlit: Web UI", 13, WHITE, False)]
c2 = [("Technical: MA/MACD/RSI/KDJ/Bollinger", 13, WHITE, False),
      ("News: Sentiment + Impact strength", 13, WHITE, False),
      ("Fundamentals: PE/PB/ROE metrics", 13, WHITE, False),
      ("Market: Shanghai/Shenzhen/Chinext", 13, WHITE, False),
      ("LLM: Multi-source synthesis + structured output", 13, WHITE, False)]
c3 = [("K-line chart + indicator overlay", 13, WHITE, False),
      ("Trend prediction (Bullish/Bearish/Neutral)", 13, WHITE, False),
      ("Confidence score (0.0-1.0)", 13, WHITE, False),
      ("Target price & support/resistance", 13, WHITE, False),
      ("Full Markdown analysis report", 13, WHITE, False)]
card(s, Inches(0.8), Inches(4.9), Inches(3.7), Inches(2.2), "Tech Stack", c1, ACCENT_BLUE)
card(s, Inches(4.8), Inches(4.9), Inches(3.7), Inches(2.2), "Analysis Dimensions", c2, ACCENT_GREEN)
card(s, Inches(8.8), Inches(4.9), Inches(3.7), Inches(2.2), "Outputs", c3, ACCENT_ORANGE)
pn(s, 10)

# ================================================================
# SLIDE 12: Data Collection Node
# ================================================================
s = new_slide()
section(s, 3, "Real Project: Stock Prediction Agent")
title_content(s, "Node 1: Data Collection",
              "Concurrent Multi-Source Fetching + Smart Caching + Timeout Protection")

c1 = [("1. AKShare real-time API for A-share data", 14, WHITE, False),
      ("2. ThreadPoolExecutor concurrent requests (K-line + Financials + News)", 14, WHITE, False),
      ("3. wait() + timeout prevents single API from blocking pipeline", 14, ACCENT_GREEN, True),
      ("4. Prefetch: main.py pre-fetches -> node reuses, avoiding duplicate calls", 14, ACCENT_ORANGE, True),
      ("5. Market index failure is non-blocking (try/except)", 14, LIGHT_GRAY, False)]
c2 = [("K-line historical data (pd.DataFrame)", 14, WHITE, False),
      ("Real-time quote (price/change%/volume)", 14, WHITE, False),
      ("Financial indicators (PE/PB/ROE/revenue growth)", 14, WHITE, False),
      ("News list (title/source/time/content)", 14, WHITE, False),
      ("Market indices (Shanghai/Shenzhen/Chinext)", 14, WHITE, False),
      ("", 8, WHITE, False),
      ("Key: partial data missing doesn't block downstream nodes", 13, ACCENT_GREEN, True),
      ("errors list collects all non-fatal errors", 13, LIGHT_GRAY, False)]
card(s, Inches(0.8), Inches(3.9), Inches(5.8), Inches(3.3), "Data Collection Strategy", c1, ACCENT_BLUE)
card(s, Inches(7.0), Inches(3.9), Inches(5.8), Inches(3.3), "Data Fetched", c2, ACCENT_GREEN)
pn(s, 11)

# ================================================================
# SLIDE 13: Technical Analysis Node
# ================================================================
s = new_slide()
section(s, 3, "Real Project: Stock Prediction Agent")
title_content(s, "Node 2: Technical Analysis",
              "Compute 6 Major Technical Indicators -> LLM Professional Interpretation")

indis = [
    ("MA Moving Avg", "5/10/20/60 day MA\nBullish/Bearish alignment"),
    ("MACD", "DIF/DEA/Histogram\nGolden/Death cross, Divergence"),
    ("RSI", "RSI6/14/24\nOverbought>70, Oversold<30"),
    ("KDJ", "K/D/J three lines\nOverbought/Oversold, Cross"),
    ("Bollinger Bands", "Upper/Mid/Lower bands\nContraction=breakout, Expansion=trend"),
    ("Volume", "Price-volume coordination\nVolume ratio"),
]
for i, (name, desc) in enumerate(indis):
    col = i % 3; row = i // 3
    x = Inches(0.8 + col * 4.1); y = Inches(3.8 + row * 1.65)
    parts = desc.split("\n")
    card(s, x, y, Inches(3.7), Inches(1.4), name,
         [(parts[0], 12, WHITE, False), (parts[1], 12, LIGHT_GRAY, False)], ACCENT_BLUE)

tb(s, Inches(0.8), Inches(7.0), Inches(11), Inches(0.4),
   "LLM Analysis Framework: Trend -> Indicators -> Support/Resistance -> Overall Score | temperature=0.1 for stable output",
   fs=12, color=LIGHT_GRAY)
pn(s, 12)

# ================================================================
# SLIDE 14: News Sentiment & Prediction Nodes
# ================================================================
s = new_slide()
section(s, 3, "Real Project: Stock Prediction Agent")
title_content(s, "Node 3 & 4: News Sentiment + Comprehensive Prediction",
              "From Multi-Source Information to Structured Decision")

c1 = [("Input: news_data (up to 15 items)", 14, WHITE, False),
      ("Analysis dimensions:", 14, ACCENT_ORANGE, True),
      ("  1. Per-item: Bullish/Bearish/Neutral + star rating", 13, LIGHT_GRAY, False),
      ("  2. Keywords: 3-5 core theme words", 13, LIGHT_GRAY, False),
      ("  3. Overall sentiment: Positive/Neutral/Negative/Mixed", 13, LIGHT_GRAY, False),
      ("  4. Major event risk alerts", 13, LIGHT_GRAY, False),
      ("No news: gracefully skip with placeholder message", 13, ACCENT_GREEN, False),
      ("temperature=0.6 -> more creative interpretation", 13, LIGHT_GRAY, False)]
c2 = [("Input: Technical + Sentiment + Fundamentals + Market", 14, ACCENT_PURPLE, True),
      ("LLM synthesis -> structured JSON output:", 14, WHITE, False),
      ('  "trend": "bullish" | "bearish" | "neutral"', 12, ACCENT_GREEN, False),
      ('  "confidence": 0.75  (0.0~1.0)', 12, ACCENT_GREEN, False),
      ('  "key_factors": [...]  (3-5 key drivers)', 12, ACCENT_GREEN, False),
      ('  "risk_warnings": [...]', 12, ACCENT_GREEN, False),
      ('  "price_targets": {support, resistance, ...}', 12, ACCENT_GREEN, False),
      ("Fault-tolerant: JSON parse failure -> multi-layer extraction -> default", 13, ACCENT_ORANGE, True),
      ("Validation: verify trend/confidence and fix if invalid", 13, LIGHT_GRAY, False)]
card(s, Inches(0.8), Inches(3.9), Inches(5.8), Inches(3.3), "Node 3: News Sentiment Analysis", c1, ACCENT_ORANGE)
card(s, Inches(7.0), Inches(3.9), Inches(5.8), Inches(3.3), "Node 4: Comprehensive Prediction", c2, ACCENT_PURPLE)
pn(s, 13)

# ================================================================
# SLIDE 15: Report Generation
# ================================================================
s = new_slide()
section(s, 3, "Real Project: Stock Prediction Agent")
title_content(s, "Node 5: Report Generation",
              "Integrate All Analysis Results into a Professional Markdown Report")

report = (
    "# Stock (CODE) Intelligent Analysis Report\n\n"
    "**Generated**: 2026-07-15 14:30:00\n"
    "**Method**: AI Multi-Source Analysis (LangGraph + LLM)\n\n"
    "| Price | Change% | Trend | Confidence |\n"
    "|-------|---------|-------|------------|\n"
    "| 1700.00 | +2.35% | Bullish | 75% |\n\n"
    "---\n\n"
    "## Executive Summary\n"
    "Technical + sentiment + fundamentals indicate short-term bullish...\n\n"
    "## Technical Analysis\n"
    "MACD golden cross formed, MA bullish alignment...\n\n"
    "## News Sentiment\n"
    "Recent positive news, north-bound capital inflows...\n\n"
    "## Fundamentals Overview\n"
    "PE 28.5 | PB 8.2 | ROE 25.3%...\n\n"
    "## Prediction\n"
    "- Trend: Bullish | Confidence: 75%\n"
    "- Support 1650 | Resistance 1750\n\n"
    "## Disclaimer\n"
    "> AI-generated, for reference only, not investment advice"
)
cs = rect(s, Inches(0.8), Inches(3.9), Inches(6.5), Inches(3.3), CODE_BG)
tf = cs.text_frame; tf.word_wrap = True
tf.paragraphs[0].text = report
tf.paragraphs[0].font.size = Pt(8)
tf.paragraphs[0].font.color.rgb = WHITE
tf.paragraphs[0].font.name = "Microsoft YaHei"

c1 = [("1. LLM integrates scattered analysis results", 13, WHITE, False),
      ("2. Auto-generates report header (price/change/trend table)", 13, LIGHT_GRAY, False),
      ("3. temperature=0.3 for professional stable output", 13, WHITE, False),
      ("4. Fallback report: partial data output even on LLM failure", 13, ACCENT_GREEN, True),
      ("", 8, WHITE, False),
      ("Output format: Markdown", 14, ACCENT_ORANGE, True),
      ("-> Streamlit renders directly", 13, LIGHT_GRAY, False),
      ("-> Supports tables, headers, quotes, lists", 13, LIGHT_GRAY, False),
      ("-> Can export to PDF/HTML", 13, LIGHT_GRAY, False)]
card(s, Inches(7.8), Inches(3.9), Inches(5.0), Inches(3.3), "Report Design Points", c1, ACCENT_PURPLE)
pn(s, 14)

# ================================================================
# SLIDE 16: Streamlit Frontend
# ================================================================
s = new_slide()
section(s, 3, "Real Project: Stock Prediction Agent")
title_content(s, "Streamlit Frontend Design",
              "Lightweight Python Web UI, Zero Frontend Code")

c1 = [("Sidebar: stock code + date + LLM config", 13, WHITE, False),
      ("Main area:", 13, ACCENT_BLUE, True),
      ("  -> Welcome guide (initial state)", 13, LIGHT_GRAY, False),
      ("  -> Progress bar (analyzing)", 13, LIGHT_GRAY, False),
      ("  -> K-line chart + indicators", 13, LIGHT_GRAY, False),
      ("  -> Prediction panel (trend+confidence+target)", 13, LIGHT_GRAY, False),
      ("  -> Analysis detail Tabs", 13, LIGHT_GRAY, False),
      ("Footer: disclaimer", 13, LIGHT_GRAY, False)]
c2 = [("st.session_state stores:", 13, ACCENT_GREEN, True),
      ("  agent_state: Agent run results", 13, LIGHT_GRAY, False),
      ("  kline_df: pre-fetched K-line data", 13, LIGHT_GRAY, False),
      ("  analysis_done: whether complete", 13, LIGHT_GRAY, False),
      ("  analysis_running: running state", 13, LIGHT_GRAY, False),
      ("", 8, WHITE, False),
      ("Priority:", 13, ACCENT_ORANGE, True),
      ("main.py pre-fetches K-line -> display chart ->", 13, LIGHT_GRAY, False),
      ("-> Agent nodes reuse pre-fetched data", 13, LIGHT_GRAY, False)]
c3 = [("st.status context manager:", 13, ACCENT_PURPLE, True),
      ("  Shows real-time analysis phase", 13, LIGHT_GRAY, False),
      ("  -> Collecting data...", 13, LIGHT_GRAY, False),
      ("  -> Technical analysis...", 13, LIGHT_GRAY, False),
      ("  -> Analysis complete!", 13, ACCENT_GREEN, False),
      ("", 8, WHITE, False),
      ("st.plotly_chart:", 13, ACCENT_BLUE, True),
      ("  Interactive K-line chart", 13, LIGHT_GRAY, False),
      ("  Supports zoom/hover/drag", 13, LIGHT_GRAY, False)]
card(s, Inches(0.8), Inches(3.9), Inches(3.7), Inches(3.3), "Page Layout", c1, ACCENT_BLUE)
card(s, Inches(4.8), Inches(3.9), Inches(3.7), Inches(3.3), "Session State", c2, ACCENT_GREEN)
card(s, Inches(8.8), Inches(3.9), Inches(3.7), Inches(3.3), "UX", c3, ACCENT_PURPLE)
pn(s, 15)

# ================================================================
# SLIDE 17: Complete Execution Flow
# ================================================================
s = new_slide()
section(s, 3, "Real Project: Stock Prediction Agent")
title_content(s, "Complete Execution Flow",
              "From user click to final report - one complete chain")

c1 = [("1. UI Layer", 14, ACCENT_BLUE, True),
      ("   User fills stock code -> clicks Analyze -> main.py pre-fetches K-line (with timeout)", 13, LIGHT_GRAY, False),
      ("   -> Inject kline_df + quote into prefetch module", 13, LIGHT_GRAY, False),
      ("", 8, WHITE, False),
      ("2. Agent Layer (run_agent)", 14, ACCENT_GREEN, True),
      ("   Build initial AgentState -> graph.invoke(initial_state)", 13, LIGHT_GRAY, False),
      ("   -> State flows through 5 nodes sequentially", 13, LIGHT_GRAY, False),
      ("", 8, WHITE, False),
      ("3. Node Layer (5 nodes)", 14, ACCENT_ORANGE, True),
      ("   data_collection -> technical_analysis -> news_sentiment -> prediction -> report", 13, LIGHT_GRAY, False),
      ("   Each node: read State -> execute business logic/LLM -> return dict to update State", 13, LIGHT_GRAY, False),
      ("", 8, WHITE, False),
      ("4. Display Layer", 14, ACCENT_PURPLE, True),
      ("   Read final_state -> K-line chart(Plotly) + prediction panel + analysis tabs + full report", 13, LIGHT_GRAY, False)]
card(s, Inches(0.8), Inches(3.9), Inches(11.5), Inches(3.3), "", c1, ACCENT_BLUE)
pn(s, 16)

# ================================================================
# SLIDE 18: Prompt Engineering
# ================================================================
s = new_slide()
section(s, 4, "Key Techniques & Lessons Learned")
title_content(s, "Prompt Engineering - The Soul of Agent",
              "Good Prompts Determine Output Quality, Format, and Consistency")

c1 = [("1. Role Setting: Give LLM professional identity", 14, WHITE, False),
      ('   "You are a senior A-share analyst with 20 years experience"', 12, ACCENT_GREEN, False),
      ("2. Structured Framework: Clear chapters and analysis dimensions", 14, WHITE, False),
      ("   Trend -> Indicators -> Support/Resistance -> Overall Score", 12, LIGHT_GRAY, False),
      ("3. Output Format Constraints: Specify expected output structure", 14, WHITE, False),
      ("   Technical report = Markdown, Prediction = JSON", 12, LIGHT_GRAY, False),
      ("4. Examples First: Give LLM reference samples", 14, WHITE, False),
      ('   "Please strictly output in the following JSON format"', 12, ACCENT_ORANGE, False)]
c2 = [("Technical Analysis: 0.1 - stable consistent output", 14, WHITE, False),
      ("Prediction: 0.1 - reduce randomness, more reliable", 14, WHITE, False),
      ("Report Generation: 0.3 - natural language but not divergent", 14, WHITE, False),
      ("News Sentiment: 0.6 - needs some creative interpretation", 14, WHITE, False),
      ("", 8, WHITE, False),
      ("Rule of thumb:", 13, ACCENT_ORANGE, True),
      ("Objective analysis -> low temperature (0.0~0.3)", 13, LIGHT_GRAY, False),
      ("Creative work -> high temperature (0.5~0.8)", 13, LIGHT_GRAY, False)]
card(s, Inches(0.8), Inches(3.9), Inches(5.8), Inches(3.3), "Prompt Design Principles", c1, ACCENT_BLUE)
card(s, Inches(7.0), Inches(3.9), Inches(5.8), Inches(3.3), "Temperature Strategy", c2, ACCENT_GREEN)
pn(s, 17)

# ================================================================
# SLIDE 19: Error Handling
# ================================================================
s = new_slide()
section(s, 4, "Key Techniques & Lessons Learned")
title_content(s, "Error Handling & Fault Tolerance Design",
              "Agent cannot crash entirely because one step fails")

c1 = [("1. Node-level try/except", 14, ACCENT_BLUE, True),
      ("   Each node independently wrapped, failure -> append errors, continue", 13, LIGHT_GRAY, False),
      ("2. Graceful degradation on missing data", 14, ACCENT_BLUE, True),
      ('   No K-line -> "Cannot analyze"; No news -> "No recent news"', 13, LIGHT_GRAY, False),
      ("3. Non-fatal errors don't block", 14, ACCENT_BLUE, True),
      ("   Market index fetch failed -> still continue analysis", 13, LIGHT_GRAY, False),
      ("4. JSON multi-layer extraction", 14, ACCENT_GREEN, True),
      ("   json.loads -> regex ```json``` -> regex { } -> default fallback", 13, LIGHT_GRAY, False)]
c2 = [("1. Data fetch: ThreadPoolExecutor + wait(timeout=N)", 14, ACCENT_ORANGE, True),
      ("   Any API hangs -> cancel after timeout", 13, LIGHT_GRAY, False),
      ("2. K-line fetch: Future.result(timeout=20)", 14, ACCENT_ORANGE, True),
      ('   No response in 20s -> prompt user "Network timeout, retry"', 13, LIGHT_GRAY, False),
      ("3. tenacity retry mechanism", 14, ACCENT_ORANGE, True),
      ("   AKShare API auto-retries 3 times, exponential backoff", 13, LIGHT_GRAY, False),
      ("", 8, WHITE, False),
      ("Core philosophy:", 13, ACCENT_GREEN, True),
      ("Better to output incomplete analysis than make users wait in vain", 14, WHITE, False)]
card(s, Inches(0.8), Inches(3.9), Inches(5.8), Inches(3.3), "Multi-layer Fault Tolerance", c1, ACCENT_BLUE)
card(s, Inches(7.0), Inches(3.9), Inches(5.8), Inches(3.3), "Timeout Protection", c2, ACCENT_ORANGE)
pn(s, 18)

# ================================================================
# SLIDE 20: Prefetch Mechanism
# ================================================================
s = new_slide()
section(s, 4, "Key Techniques & Lessons Learned")
title_content(s, "Prefetch Mechanism - Bypassing Serialization Limits",
              "Solving the problem of LangGraph msgpack unable to serialize pd.DataFrame")

c1 = [("The Problem:", 14, ACCENT_ORANGE, True),
      ("LangGraph internally uses msgpack to serialize State", 14, ACCENT_ORANGE, True),
      ("pd.DataFrame does NOT support msgpack serialization", 14, ACCENT_ORANGE, True),
      ("Putting it directly in State -> RuntimeError", 14, ACCENT_ORANGE, True),
      ("", 8, WHITE, False),
      ("Solution: Prefetch Module", 14, ACCENT_GREEN, True),
      ("1. main.py fetches DataFrame first", 14, WHITE, False),
      ("2. Store in module-level variable _pre_fetched", 14, WHITE, False),
      ("3. data_collection_node reads from variable, bypasses State", 14, WHITE, False),
      ("4. State's kline_data typed as Optional[Any]", 14, WHITE, False)]
c2 = [("1. TypedDict total=False", 13, ACCENT_GREEN, True),
      ("   All fields optional, nodes return only their own keys", 13, LIGHT_GRAY, False),
      ("2. invoke() initial state must cover all required fields", 13, ACCENT_ORANGE, True),
      ("   Otherwise KeyError -> use total=False with .get()", 13, LIGHT_GRAY, False),
      ("3. Graph cannot be modified after compile()", 13, ACCENT_PURPLE, True),
      ("   All nodes/edges must be added before compile()", 13, LIGHT_GRAY, False),
      ("4. draw_png() needs Graphviz on Windows", 13, ACCENT_ORANGE, True),
      ("   Recommended: use draw_mermaid() instead", 13, LIGHT_GRAY, False),
      ("5. LLM API Key should NOT be hardcoded", 13, ACCENT_ORANGE, True),
      ("   Pass via UI input or environment variable", 13, LIGHT_GRAY, False)]
card(s, Inches(0.8), Inches(3.9), Inches(5.8), Inches(3.3), "The Problem & Solution", c1, ACCENT_BLUE)
card(s, Inches(7.0), Inches(3.9), Inches(5.8), Inches(3.3), "Other Lessons Learned", c2, ACCENT_GREEN)
pn(s, 19)

# ================================================================
# SLIDE 21: Summary & Learning Path
# ================================================================
s = new_slide()
title_content(s, "Summary & Learning Path",
              "Core competencies for building LangGraph Agents from scratch")

items = [
    ("Phase 1: Core Concepts", ACCENT_BLUE, [
        "StateGraph / State / Nodes / Edges / Conditional Edges",
        "compile() / invoke() / stream()",
        "Graph visualization & debug methods",
    ]),
    ("Phase 2: Hands-on Practice", ACCENT_GREEN, [
        "Start with simple 3-node demo (input->process->output)",
        "Add conditional routing, experience Agent decision-making",
        "Gradually expand node count and analysis dimensions",
    ]),
    ("Phase 3: Production", ACCENT_ORANGE, [
        "Prompt Engineering: role setting, structured output, format constraints",
        "Fault tolerance: multi-layer try/except, timeout, retry, fallback",
        "Frontend-backend integration: Streamlit UI + LangGraph backend",
    ]),
    ("Phase 4: Advanced", ACCENT_PURPLE, [
        "Multi-Agent collaboration (Supervisor + Worker pattern)",
        "Human-in-the-loop (manual review nodes)",
        "Long-term memory & RAG knowledge base",
        "Checkpoint persistence & resume from breakpoint",
    ]),
]
for i, (ttl, color, lines) in enumerate(items):
    x = Inches(0.8 + i * 3.15)
    body = [(l, 11, WHITE if j == 0 else LIGHT_GRAY, False) for j, l in enumerate(lines)]
    card(s, x, Inches(3.6), Inches(2.85), Inches(3.2), ttl, body, color)

line(s, Inches(0.8), Inches(7.0), Inches(11.5), ACCENT_BLUE)
tb(s, Inches(0.8), Inches(7.05), Inches(11.5), Inches(0.3),
   "The value of an Agent lies not in the model itself, but in how you orchestrate it to solve problems",
   fs=13, color=ACCENT_BLUE, bold=True, align=PP_ALIGN.CENTER)
pn(s, 20)

# ================================================================
# Save
# ================================================================
out = r"c:\Users\Y Henry\Documents\stock-prediction-agent\LangChain_LangGraph_Agent.pptx"
prs.save(out)
print(f"PPT saved: {out}")
print(f"Total slides: {len(prs.slides)}")
