"""自定义 Streamlit CSS —— 「Aurora Terminal」深色金融终端风

设计 token 与 design/ui_mockup.html 一一对应，改色请两处一起改。
配色经过校验：涨 #ff5d6c / 跌 #16c98d 在 #10151e 上分别约 5.9:1、7.4:1；
两者色盲区分度仍落在警告带，所以任何涨跌色**必须**同时带 ▲▼ 或正负号。
"""
import streamlit as st

_TOKENS = """
:root{
  --bg:#070a0f;
  --bg-2:#0a0e15;
  --surface:#10151e;
  --surface-2:#151b26;
  --surface-3:#1b2230;
  --line:rgba(255,255,255,.07);
  --line-strong:rgba(255,255,255,.13);
  --grid:rgba(255,255,255,.045);
  --ink-1:#eef2f9;
  --ink-2:#a8b3c7;
  --ink-3:#6f7c92;
  --up:#ff5d6c;
  --down:#16c98d;
  --accent:#7c8cff;
  --accent-2:#22d3ee;
  --gold:#f5b544;
  --focus:#7c8cff;
  --radius:14px;
  --radius-sm:10px;
  --mono:"JetBrains Mono","SFMono-Regular",Consolas,"Liberation Mono",monospace;
  --sans:"Inter","PingFang SC","Microsoft YaHei",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}
"""

_BASE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html,body,[class*="css"]{font-family:var(--sans);}
.stApp{
  background:
    radial-gradient(1100px 620px at 12% -8%, rgba(124,140,255,.13), transparent 62%),
    radial-gradient(900px 520px at 92% 4%, rgba(34,211,238,.09), transparent 60%),
    radial-gradient(800px 600px at 50% 108%, rgba(124,140,255,.06), transparent 65%),
    var(--bg);
  color:var(--ink-1);
}
[data-testid="stHeader"]{background:transparent;}
[data-testid="stToolbarActions"],
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"]{display:none;}
#MainMenu,footer{visibility:hidden;}

.block-container{padding-top:1.6rem;padding-bottom:3.5rem;max-width:1480px;}

::-webkit-scrollbar{width:9px;height:9px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.10);border-radius:99px;}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,.18);}

/* ===== 侧边栏 ===== */
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#0b0f16 0%,#080b11 100%);
  border-right:1px solid var(--line);
}
[data-testid="stSidebar"] .block-container,
[data-testid="stSidebarUserContent"]{padding-top:1.1rem;}
[data-testid="stSidebar"] hr{border-color:var(--line);margin:.7rem 0;}
[data-testid="stSidebar"] h2{
  font-size:.66rem;font-weight:600;letter-spacing:.16em;color:var(--ink-3);
  text-transform:uppercase;margin:16px 0 9px;padding-bottom:8px;
  border-bottom:1px solid var(--line);
}
[data-testid="stSidebar"] h2:first-child{margin-top:0;}

.brand{
  display:flex;align-items:center;gap:11px;padding:2px 2px 14px;
  margin-bottom:6px;border-bottom:1px solid var(--line);
}
.brand-mark{
  width:36px;height:36px;border-radius:11px;flex:none;
  display:grid;place-items:center;font-size:17px;
  background:linear-gradient(140deg,var(--accent),#4f5fd6 55%,var(--accent-2));
  box-shadow:0 6px 18px rgba(124,140,255,.35), inset 0 1px 0 rgba(255,255,255,.25);
}
.brand-text b{display:block;font-size:.9rem;font-weight:600;color:var(--ink-1);letter-spacing:.01em;}
.brand-text span{display:block;font-size:.66rem;color:var(--ink-3);letter-spacing:.1em;margin-top:2px;}

h1,h2,h3,h4{color:var(--ink-1);letter-spacing:-.01em;font-family:var(--sans);}
h1{font-size:1.5rem;font-weight:700;}
h2{font-size:1.12rem;font-weight:600;}
h3{font-size:.98rem;font-weight:600;}
p,li,.stMarkdown{color:var(--ink-2);}
a{color:var(--accent);text-decoration:none;}
a:hover{text-decoration:underline;}
[data-testid="stCaptionContainer"],.stCaption{color:var(--ink-3);}
[data-testid="stCaptionContainer"] p,.stCaption p{color:inherit!important;}
hr{border-color:var(--line);}
"""

_WIDGETS = """
/* ===== 按钮 ===== */
.stButton>button, .stDownloadButton>button{
  border-radius:var(--radius-sm);border:1px solid var(--line-strong);
  background:var(--surface-2);color:var(--ink-1);
  font-size:.85rem;font-weight:500;padding:.46rem .95rem;
  transition:transform .16s ease, background .16s ease, border-color .16s ease, box-shadow .16s ease;
}
.stButton>button:hover, .stDownloadButton>button:hover{
  background:var(--surface-3);border-color:rgba(124,140,255,.45);
  color:var(--ink-1);transform:translateY(-1px);
  box-shadow:0 6px 18px rgba(0,0,0,.35);
}
.stButton>button:active{transform:translateY(0);}
.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,var(--accent) 0%,#5b6ae0 100%);
  border-color:transparent;color:#fff;font-weight:600;
  box-shadow:0 8px 22px rgba(124,140,255,.32), inset 0 1px 0 rgba(255,255,255,.22);
}
.stButton>button[kind="primary"]:hover{
  background:linear-gradient(135deg,#8b99ff 0%,#6a78ea 100%);
  box-shadow:0 10px 28px rgba(124,140,255,.45), inset 0 1px 0 rgba(255,255,255,.28);
  color:#fff;
}
.stButton>button:disabled{opacity:.4;transform:none;box-shadow:none;}
.stButton>button p,.stDownloadButton>button p,.stFormSubmitButton>button p{color:inherit!important;}
.stFormSubmitButton>button{
  border-radius:var(--radius-sm);border:1px solid var(--line-strong);
  background:var(--surface-2);color:var(--ink-1);
}
.stFormSubmitButton>button:hover{background:var(--surface-3);border-color:rgba(124,140,255,.45);}

/* ===== 输入控件 ===== */
.stTextInput input,.stNumberInput input,.stDateInput input{
  background:var(--surface-2)!important;color:var(--ink-1)!important;
  border:1px solid var(--line)!important;border-radius:var(--radius-sm)!important;
  font-size:.85rem!important;transition:border-color .16s ease, box-shadow .16s ease;
}
.stTextInput input:focus,.stNumberInput input:focus,.stDateInput input:focus{
  border-color:rgba(124,140,255,.6)!important;
  box-shadow:0 0 0 3px rgba(124,140,255,.14)!important;
}
div[data-baseweb="select"]>div{
  background:var(--surface-2)!important;border-color:var(--line)!important;
  border-radius:var(--radius-sm)!important;color:var(--ink-1)!important;
  font-size:.85rem!important;
}
div[data-baseweb="select"]>div:hover{border-color:var(--line-strong)!important;}
div[data-baseweb="popover"] ul{background:var(--surface-2)!important;}
div[data-baseweb="popover"] li:hover{background:var(--surface-3)!important;}
label,.stRadio label,.stCheckbox label{color:var(--ink-2)!important;font-size:.8rem!important;}

/* 单选：胶囊分段控件 */
[data-testid="stSidebar"] .stRadio [role="radiogroup"]{gap:6px;}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label{
  background:var(--surface-2);border:1px solid var(--line);
  border-radius:var(--radius-sm);padding:9px 12px;margin:0;
  transition:all .16s ease;cursor:pointer;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:hover{
  background:var(--surface-3);border-color:var(--line-strong);
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:has(input:checked){
  background:linear-gradient(135deg,rgba(124,140,255,.22),rgba(34,211,238,.10));
  border-color:rgba(124,140,255,.55);
  box-shadow:0 4px 16px rgba(124,140,255,.18);
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label:has(input:checked) p{
  color:var(--ink-1)!important;font-weight:600;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label>div:first-child{display:none;}

[data-testid="stCheckbox"] label span,
[data-testid="stToggle"] label span{color:var(--ink-2)!important;}

/* ===== 展开器 ===== */
[data-testid="stExpander"] details{
  background:var(--surface);border:1px solid var(--line)!important;
  border-radius:var(--radius)!important;overflow:hidden;
  transition:border-color .16s ease;
}
[data-testid="stExpander"] details:hover{border-color:var(--line-strong)!important;}
[data-testid="stExpander"] summary{color:var(--ink-2);font-size:.84rem;padding:.6rem .9rem;}
[data-testid="stExpander"] summary:hover{color:var(--ink-1);}

/* ===== 标签页：胶囊 ===== */
.stTabs [data-baseweb="tab-list"]{
  gap:6px;border-bottom:1px solid var(--line);padding-bottom:8px;
  background:transparent;flex-wrap:wrap;
}
.stTabs [data-baseweb="tab"]{
  background:var(--surface);color:var(--ink-3);
  border:1px solid var(--line);border-radius:99px;
  padding:.4rem .9rem;font-size:.82rem;height:auto;
  transition:all .16s ease;
}
.stTabs [data-baseweb="tab"]:hover{color:var(--ink-1);border-color:var(--line-strong);}
.stTabs [aria-selected="true"]{
  background:linear-gradient(135deg,rgba(124,140,255,.24),rgba(34,211,238,.10));
  color:var(--ink-1)!important;border-color:rgba(124,140,255,.5);
  font-weight:600;
}
.stTabs [data-baseweb="tab-highlight"]{display:none;}
.stTabs [data-baseweb="tab-border"]{display:none;}

/* ===== 进度条 ===== */
.stProgress>div>div>div>div{
  background:linear-gradient(90deg,var(--accent),var(--accent-2));
  border-radius:99px;
}
.stProgress>div>div>div{background:var(--surface-3);border-radius:99px;}

/* ===== 提示框 ===== */
[data-testid="stAlert"]{
  background:var(--surface);border:1px solid var(--line);
  border-left-width:3px;border-radius:var(--radius-sm);color:var(--ink-2);
  font-size:.84rem;
}
[data-testid="stAlertContainer"]{background:transparent!important;}
[data-testid="stAlert"]:has([data-testid*="ContentInfo"]){border-left-color:var(--accent);}
[data-testid="stAlert"]:has([data-testid*="ContentSuccess"]){border-left-color:var(--down);}
[data-testid="stAlert"]:has([data-testid*="ContentWarning"]){border-left-color:var(--gold);}
[data-testid="stAlert"]:has([data-testid*="ContentError"]){border-left-color:var(--up);}
[data-testid="stNotification"]{background:var(--surface-2);}

/* ===== 边框容器 = 卡片 ===== */
[data-testid="stVerticalBlockBorderWrapper"]{
  background:linear-gradient(180deg,rgba(255,255,255,.028),rgba(255,255,255,.012));
  border:1px solid var(--line)!important;
  border-radius:var(--radius);
  box-shadow:0 1px 0 rgba(255,255,255,.03) inset, 0 10px 30px rgba(0,0,0,.22);
  transition:border-color .18s ease, box-shadow .18s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover{
  border-color:var(--line-strong)!important;
  box-shadow:0 1px 0 rgba(255,255,255,.04) inset, 0 14px 38px rgba(0,0,0,.3);
}

/* ===== 弹窗 ===== */
div[role="dialog"]{
  background:linear-gradient(180deg,#121824,#0d121a)!important;
  border:1px solid var(--line-strong);border-radius:18px;
  box-shadow:0 40px 100px rgba(0,0,0,.7);
}

/* ===== 指标 metric ===== */
[data-testid="stMetric"]{
  background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius-sm);padding:12px 14px;
}
[data-testid="stMetricLabel"] p{color:var(--ink-3)!important;font-size:.74rem!important;}
[data-testid="stMetricValue"]{color:var(--ink-1)!important;font-size:1.25rem!important;
  font-variant-numeric:tabular-nums;font-weight:600;}

/* ===== 表格 ===== */
[data-testid="stDataFrame"]{
  border:1px solid var(--line);border-radius:var(--radius-sm);overflow:hidden;
}

/* ===== 聊天 ===== */
[data-testid="stChatMessage"]{
  background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:14px 16px;
}
[data-testid="stChatInput"] textarea{
  background:var(--surface-2)!important;color:var(--ink-1)!important;
  border-radius:var(--radius-sm)!important;
}
[data-testid="stChatInput"]{
  border:1px solid var(--line-strong);border-radius:var(--radius);
  background:var(--surface);
}
"""

_COMPONENTS = """
/* ===== 顶部 Hero ===== */
.hero{
  position:relative;overflow:hidden;
  display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap;
  padding:22px 24px;margin-bottom:18px;
  border:1px solid var(--line);border-radius:18px;
  background:
    radial-gradient(700px 240px at 0% 0%, rgba(124,140,255,.20), transparent 70%),
    radial-gradient(600px 220px at 100% 100%, rgba(34,211,238,.12), transparent 70%),
    linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.008));
  box-shadow:0 18px 50px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.06);
}
.hero::after{
  content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.05),transparent);
  transform:translateX(-100%);animation:sheen 7s ease-in-out infinite;
}
@keyframes sheen{0%,70%{transform:translateX(-100%);}100%{transform:translateX(100%);}}
.hero-main{position:relative;z-index:1;min-width:0;}
.hero-eyebrow{
  display:inline-flex;align-items:center;gap:7px;
  font-size:.66rem;letter-spacing:.18em;text-transform:uppercase;
  color:var(--accent-2);margin-bottom:9px;font-weight:600;
}
.hero-eyebrow::before{
  content:"";width:16px;height:1px;background:var(--accent-2);opacity:.7;
}
.hero h1{
  margin:0;font-size:1.72rem;font-weight:700;letter-spacing:-.02em;
  background:linear-gradient(100deg,#ffffff 10%,#c9d2ff 55%,#8fe6f5 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent;
}
.hero .sub{
  margin:8px 0 0;font-size:.8rem;color:var(--ink-3);
  display:flex;align-items:center;gap:8px;flex-wrap:wrap;
}
.hero .sub .dot{width:3px;height:3px;border-radius:50%;background:var(--ink-3);opacity:.6;}
.hero-side{position:relative;z-index:1;margin-left:auto;display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.hero-price{text-align:right;}
.hero-price .p{font-size:1.9rem;font-weight:700;letter-spacing:-.02em;
  font-variant-numeric:tabular-nums;line-height:1.1;}
.hero-price .d{font-size:.8rem;font-weight:600;margin-top:3px;font-variant-numeric:tabular-nums;}

.term-badge{
  display:inline-flex;align-items:center;gap:7px;
  font-size:.72rem;color:var(--ink-2);border:1px solid var(--line-strong);
  border-radius:99px;padding:5px 12px;
  background:rgba(255,255,255,.04);backdrop-filter:blur(8px);
  white-space:nowrap;
}
.term-badge .live{
  width:6px;height:6px;border-radius:50%;background:var(--down);
  box-shadow:0 0 0 0 rgba(22,201,141,.6);animation:pulse-dot 2s infinite;
}
@keyframes pulse-dot{
  0%{box-shadow:0 0 0 0 rgba(22,201,141,.55);}
  70%{box-shadow:0 0 0 7px rgba(22,201,141,0);}
  100%{box-shadow:0 0 0 0 rgba(22,201,141,0);}
}
.chip{
  display:inline-flex;align-items:center;gap:6px;
  font-size:.7rem;color:var(--ink-2);
  border:1px solid var(--line);border-radius:8px;
  padding:3px 9px;background:var(--surface-2);
  font-variant-numeric:tabular-nums;
}
.chip.accent{color:#c3caff;border-color:rgba(124,140,255,.35);background:rgba(124,140,255,.10);}

/* ===== 行情条 ===== */
.quote-strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px;}
.quote-card{
  position:relative;overflow:hidden;
  background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.012));
  border:1px solid var(--line);border-radius:var(--radius);
  padding:14px 16px;transition:transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}
.quote-card::before{
  content:"";position:absolute;left:0;top:0;bottom:0;width:2px;
  background:linear-gradient(180deg,var(--accent),transparent);
  opacity:0;transition:opacity .18s ease;
}
.quote-card:hover{
  transform:translateY(-2px);border-color:var(--line-strong);
  box-shadow:0 14px 34px rgba(0,0,0,.35);
}
.quote-card:hover::before{opacity:1;}
.quote-top{display:flex;align-items:baseline;gap:8px;}
.quote-name{font-weight:600;font-size:.88rem;color:var(--ink-1);}
.quote-code{font:.7rem/1 var(--mono);color:var(--ink-3);}
.quote-badge{
  margin-left:auto;font-size:.64rem;color:var(--ink-3);
  border:1px solid var(--line);border-radius:5px;padding:1px 6px;
}
.quote-price-row{display:flex;align-items:baseline;gap:9px;margin-top:6px;}
.quote-price{font-size:1.5rem;font-weight:700;letter-spacing:-.02em;
  color:var(--ink-1);font-variant-numeric:tabular-nums;}
.quote-meta{font-size:.71rem;color:var(--ink-3);margin-top:4px;
  font-variant-numeric:tabular-nums;}
.delta{font-size:.78rem;font-weight:600;font-variant-numeric:tabular-nums;}
.delta.up{color:var(--up);}
.delta.down{color:var(--down);}
.delta.flat{color:var(--ink-2);}
.quote-empty{color:var(--ink-3);font-size:.78rem;margin-top:8px;}

/* ===== 分区标题 ===== */
.section-label{
  display:flex;align-items:center;gap:10px;
  font-size:.66rem;letter-spacing:.16em;color:var(--ink-3);
  text-transform:uppercase;margin:22px 0 10px;font-weight:600;
}
.section-label::after{content:"";flex:1;height:1px;
  background:linear-gradient(90deg,var(--line),transparent);}
.section-label:first-child{margin-top:0;}
.section-label .n{
  display:grid;place-items:center;width:18px;height:18px;border-radius:6px;
  font-size:.6rem;color:#c3caff;background:rgba(124,140,255,.16);
  border:1px solid rgba(124,140,255,.3);letter-spacing:0;
}
.lead{font-size:.95rem;color:var(--ink-1);line-height:1.7;}
.prose{font-size:.88rem;color:var(--ink-2);line-height:1.8;}
.prose strong{color:var(--ink-1);}

/* ===== 事件时间线 ===== */
.tl{list-style:none;margin:0;padding:0;}
.tl-item{display:grid;grid-template-columns:9px 1fr;gap:11px;
  padding-bottom:14px;position:relative;}
.tl-item:last-child{padding-bottom:0;}
.tl-item::before{content:"";position:absolute;left:4px;top:12px;bottom:0;
  width:1px;background:var(--line);}
.tl-item:last-child::before{display:none;}
.tl-dot{width:9px;height:9px;border-radius:50%;background:var(--surface-3);
  border:1px solid var(--line-strong);margin-top:4px;}
.tl-dot.hot{background:var(--accent);border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(124,140,255,.16);}
.tl-date{font:.66rem/1.6 var(--mono);color:var(--ink-3);}
.tl-title{font-size:.81rem;color:var(--ink-1);line-height:1.55;}
.tl-src{font-size:.7rem;color:var(--ink-3);margin-top:2px;}

/* ===== KPI ===== */
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;}
.kpi{
  position:relative;overflow:hidden;
  background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.012));
  border:1px solid var(--line);border-radius:var(--radius);
  padding:14px 16px;transition:transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}
.kpi::before{
  content:"";position:absolute;left:0;right:0;top:0;height:2px;
  background:linear-gradient(90deg,var(--accent),var(--accent-2));
  opacity:.55;
}
.kpi:hover{transform:translateY(-2px);border-color:var(--line-strong);
  box-shadow:0 14px 34px rgba(0,0,0,.32);}
.kpi-label{font-size:.72rem;color:var(--ink-3);letter-spacing:.02em;}
.kpi-value{font-size:1.42rem;font-weight:700;margin-top:5px;color:var(--ink-1);
  font-variant-numeric:tabular-nums;letter-spacing:-.02em;}
.kpi-note{font-size:.7rem;color:var(--ink-3);margin-top:3px;}
.kpi-value.up{color:var(--up);}
.kpi-value.down{color:var(--down);}

/* ===== 预测 Hero 卡 ===== */
.pred-hero{
  position:relative;overflow:hidden;
  display:flex;align-items:center;gap:26px;flex-wrap:wrap;
  padding:24px 26px;border-radius:18px;
  border:1px solid var(--line);
  background:
    radial-gradient(600px 220px at 0% 0%, rgba(124,140,255,.16), transparent 70%),
    linear-gradient(180deg,rgba(255,255,255,.04),rgba(255,255,255,.01));
  box-shadow:0 18px 50px rgba(0,0,0,.32), inset 0 1px 0 rgba(255,255,255,.06);
}
.pred-hero.bullish{border-color:rgba(255,93,108,.28);}
.pred-hero.bearish{border-color:rgba(22,201,141,.28);}
.pred-hero.neutral{border-color:rgba(245,181,68,.26);}
.pred-left{min-width:0;flex:1;}
.pred-kicker{font-size:.66rem;letter-spacing:.18em;text-transform:uppercase;
  color:var(--ink-3);font-weight:600;}
.pred-trend{
  display:flex;align-items:center;gap:12px;margin-top:8px;
  font-size:2.1rem;font-weight:700;letter-spacing:-.02em;line-height:1.1;
}
.pred-trend .ico{font-size:1.7rem;}
.pred-trend.up{color:var(--up);}
.pred-trend.down{color:var(--down);}
.pred-trend.warn{color:var(--gold);}
.pred-meta{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;}

.conf-ring{
  --p:50;
  width:118px;height:118px;border-radius:50%;flex:none;
  display:grid;place-items:center;position:relative;
  background:conic-gradient(var(--accent) calc(var(--p)*1%), rgba(255,255,255,.07) 0);
  box-shadow:0 0 0 1px rgba(255,255,255,.05), 0 10px 30px rgba(124,140,255,.18);
}
.conf-ring::after{
  content:"";position:absolute;inset:9px;border-radius:50%;
  background:#0d121a;border:1px solid rgba(255,255,255,.05);
}
.conf-inner{position:relative;z-index:1;text-align:center;}
.conf-inner b{display:block;font-size:1.5rem;font-weight:700;color:var(--ink-1);
  font-variant-numeric:tabular-nums;letter-spacing:-.02em;}
.conf-inner span{display:block;font-size:.62rem;color:var(--ink-3);
  letter-spacing:.1em;margin-top:1px;}

.factor-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px;}
.factor-list li{
  display:flex;gap:9px;align-items:flex-start;
  font-size:.84rem;line-height:1.6;color:var(--ink-2);
  padding:9px 12px;border-radius:var(--radius-sm);
  background:rgba(255,255,255,.025);border:1px solid var(--line);
}
.factor-list li .b{flex:none;width:5px;height:5px;border-radius:50%;
  background:var(--accent);margin-top:8px;}
.factor-list.risk li .b{background:var(--gold);}

.range-wrap{margin:34px 0 6px;}
.range-bar{position:relative;height:8px;border-radius:99px;
  background:linear-gradient(90deg,var(--down),#3a4354 50%,var(--up));
  box-shadow:inset 0 1px 2px rgba(0,0,0,.4);}
.range-mark{position:absolute;top:-26px;transform:translateX(-50%);
  white-space:nowrap;font-size:.72rem;color:var(--ink-1);font-weight:600;
  font-variant-numeric:tabular-nums;}
.range-mark::after{content:"";display:block;width:2px;height:14px;margin:3px auto 0;
  background:var(--ink-1);border-radius:1px;box-shadow:0 0 8px rgba(255,255,255,.5);}
.range-ends{display:flex;justify-content:space-between;margin-top:8px;
  font-size:.7rem;color:var(--ink-3);font-variant-numeric:tabular-nums;}

/* ===== 步骤条 ===== */
.stepper{display:flex;align-items:flex-start;gap:0;margin:6px 0 4px;}
.step{flex:1;display:flex;flex-direction:column;align-items:center;position:relative;}
.step::before{
  content:"";position:absolute;top:13px;left:50%;width:100%;height:1px;
  background:var(--line);
}
.step:last-child::before{display:none;}
.step.done::before{background:linear-gradient(90deg,var(--down),rgba(22,201,141,.3));}
.step-dot{
  position:relative;z-index:1;
  width:27px;height:27px;border-radius:50%;display:grid;place-items:center;
  font-size:.7rem;font-weight:700;
  background:var(--surface-3);color:var(--ink-3);
  border:1px solid var(--line-strong);transition:all .2s ease;
}
.step-dot-active{
  background:linear-gradient(135deg,var(--accent),#5b6ae0);color:#fff;
  border-color:transparent;box-shadow:0 0 0 4px rgba(124,140,255,.16);
  animation:pulse-step 1.6s ease-in-out infinite;
}
@keyframes pulse-step{
  0%,100%{box-shadow:0 0 0 4px rgba(124,140,255,.16);}
  50%{box-shadow:0 0 0 8px rgba(124,140,255,.05);}
}
.step-dot-done{background:rgba(22,201,141,.16);color:var(--down);
  border-color:rgba(22,201,141,.4);}
.step-label{font-size:.7rem;color:var(--ink-3);margin-top:7px;text-align:center;
  white-space:nowrap;}
.step-label.active{color:var(--ink-1);font-weight:600;}

/* ===== 空状态 ===== */
.empty-hero{text-align:center;padding:34px 20px 30px;}
.empty-hero .ico{
  width:56px;height:56px;border-radius:16px;margin:0 auto 16px;
  display:grid;place-items:center;font-size:24px;
  background:linear-gradient(140deg,rgba(124,140,255,.22),rgba(34,211,238,.10));
  border:1px solid rgba(124,140,255,.3);
  box-shadow:0 10px 30px rgba(124,140,255,.18);
}
.empty-hero h3{margin:0 0 8px;font-size:1.05rem;color:var(--ink-1);}
.empty-hero p{margin:0;font-size:.85rem;color:var(--ink-3);line-height:1.8;}
.flow-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
  gap:10px;margin-top:22px;text-align:left;}
.flow-item{
  padding:13px 15px;border-radius:var(--radius-sm);
  background:rgba(255,255,255,.025);border:1px solid var(--line);
  transition:border-color .18s ease, transform .18s ease;
}
.flow-item:hover{border-color:rgba(124,140,255,.35);transform:translateY(-2px);}
.flow-item .n{font:.66rem/1 var(--mono);color:var(--accent);letter-spacing:.1em;}
.flow-item .t{font-size:.84rem;color:var(--ink-1);font-weight:600;margin-top:6px;}
.flow-item .d{font-size:.72rem;color:var(--ink-3);margin-top:3px;line-height:1.6;}

/* ===== 套餐卡 ===== */
.plan-card{background:var(--surface-2);border:1px solid var(--line);
  border-radius:var(--radius);padding:13px 15px;}
.plan-row{display:flex;justify-content:space-between;align-items:baseline;
  font-size:.78rem;color:var(--ink-2);}
.plan-name{color:var(--accent);font-weight:600;}
.plan-usage{font:.7rem/1 var(--mono);color:var(--ink-3);}
.plan-bar{height:5px;border-radius:99px;background:var(--surface-3);
  margin-top:9px;overflow:hidden;}
.plan-bar>i{display:block;height:100%;border-radius:99px;
  background:linear-gradient(90deg,var(--accent),var(--accent-2));}

/* ===== 免责 ===== */
.disclaimer{border-top:1px solid var(--line);padding-top:12px;margin-top:18px;
  font-size:.72rem;color:var(--ink-3);line-height:1.7;}
.disclaimer b{color:var(--ink-2);font-weight:500;}

/* ===== 兼容旧组件 ===== */
.main-header{font-size:1.5rem;font-weight:700;color:var(--ink-1);margin:0;}
.prediction-card{border-radius:var(--radius);padding:1.1rem;margin:.6rem 0;
  border:1px solid var(--line);background:var(--surface);border-left-width:3px;}
.prediction-bullish{border-left-color:var(--up);}
.prediction-bearish{border-left-color:var(--down);}
.prediction-neutral{border-left-color:var(--gold);}
.metric-card{text-align:center;padding:.95rem;border-radius:var(--radius-sm);
  background:var(--surface);border:1px solid var(--line);}
.metric-value{font-size:1.3rem;font-weight:600;color:var(--ink-1);
  font-variant-numeric:tabular-nums;}
.metric-label{font-size:.75rem;color:var(--ink-3);}
.metric-up{color:var(--up);}
.metric-down{color:var(--down);}
.metric-warn{color:var(--gold);}
.metric-value.up{color:var(--up);}
.metric-value.down{color:var(--down);}
.metric-value.warn{color:var(--gold);}
.risk-warning{background:var(--surface);border:1px solid var(--line);
  border-left:3px solid var(--gold);border-radius:var(--radius-sm);
  padding:.9rem;margin-top:1rem;}
"""

_METEOR = """
/* ===== 背景流星雨 =====
   整层 fixed + z-index:-1，落在 .stApp 这个 isolation 栈的底部：
   在页面渐变背景之上、所有正文之下 —— 看得见，但永远点不到、盖不住字。
   颜色只取冷色（白/淡蓝/青），与 --accent / --accent-2 同族，亮度压得很低。 */
/* ⚠️ 关键：这里绝对不能写 position:relative。
   Streamlit 的 .stApp 默认是 position:absolute; inset:0，靠它撑满视口；
   一旦改成 relative，.stApp 高度会塌成 0，里面的 stAppViewContainer
   （overflow:hidden）跟着变 0 高，整页正文就被裁没了 —— 只剩背景。
   我们只需要 isolation:isolate 来建立层叠上下文，让 z-index:-1 的流星层
   留在 .stApp 内部、位于正文之下。 */
.stApp{isolation:isolate;background:transparent;}

/* 页面渐变背景下沉到 z-index:-2 的固定层，
   这样流星层（-1）才能夹在「背景」和「正文」之间 —— 看得见又不挡字。 */
.stApp::before{
  content:"";position:fixed;inset:0;z-index:-2;pointer-events:none;
  background:
    radial-gradient(1100px 620px at 12% -8%, rgba(124,140,255,.13), transparent 62%),
    radial-gradient(900px 520px at 92% 4%, rgba(34,211,238,.09), transparent 60%),
    radial-gradient(800px 600px at 50% 108%, rgba(124,140,255,.06), transparent 65%),
    var(--bg);
}

.meteor-field{
  position:fixed;inset:0;z-index:-1;overflow:hidden;
  pointer-events:none;user-select:none;
  contain:strict;
}
.meteor-field *{pointer-events:none;}

/* 极光雾：给流星雨一层很淡的冷色底，避免流星像贴在纯黑上 */
.meteor-nebula{
  position:absolute;inset:-10%;
  background:
    radial-gradient(60% 45% at 18% 8%, rgba(124,140,255,.10), transparent 70%),
    radial-gradient(55% 40% at 88% 22%, rgba(34,211,238,.07), transparent 72%),
    radial-gradient(70% 50% at 50% 100%, rgba(124,140,255,.05), transparent 75%);
  filter:blur(6px);
  animation:nebula-drift 26s ease-in-out infinite alternate;
}
@keyframes nebula-drift{
  0%{transform:translate3d(0,0,0) scale(1);}
  100%{transform:translate3d(-1.5%,1.2%,0) scale(1.04);}
}

/* 星点 */
.meteor-field .s{
  position:absolute;left:var(--x);top:var(--y);
  width:var(--sz);height:var(--sz);border-radius:50%;
  background:#e8f0ff;
  opacity:var(--o);
  box-shadow:0 0 4px rgba(200,220,255,.55);
  animation:star-twinkle var(--d) ease-in-out var(--dl) infinite;
  will-change:opacity,transform;
}
@keyframes star-twinkle{
  0%,100%{opacity:calc(var(--o) * .35);transform:scale(.85);}
  50%{opacity:var(--o);transform:scale(1.15);}
}

/* 流星本体：一条带渐隐尾迹的细线，头部在右端 */
.meteor-field .m{
  position:absolute;left:var(--x);top:var(--y);
  width:var(--len);height:var(--th);
  border-radius:99px;
  /* 老浏览器兜底：不支持 color-mix 时用半透明白 */
  background:linear-gradient(90deg, transparent 0%, rgba(255,255,255,.22) 45%, var(--c) 100%);
  background:linear-gradient(90deg,
    transparent 0%,
    color-mix(in srgb, var(--c) 45%, transparent) 45%,
    var(--c) 100%);
  box-shadow:0 0 10px rgba(200,220,255,.55), 0 0 22px rgba(160,200,255,.28);
  box-shadow:0 0 10px color-mix(in srgb, var(--c) 70%, transparent),
             0 0 22px color-mix(in srgb, var(--c) 35%, transparent);
  opacity:0;
  transform:rotate(38deg);
  transform-origin:100% 50%;
  animation:meteor-fall var(--dur) linear var(--delay) infinite;
  will-change:transform,opacity;
}
/* 头部亮点 */
.meteor-field .m::after{
  content:"";position:absolute;right:-1px;top:50%;
  width:calc(var(--th) * 2.2);height:calc(var(--th) * 2.2);
  transform:translate(50%,-50%);
  border-radius:50%;
  background:radial-gradient(circle, #fff 0%, var(--c) 45%, transparent 72%);
  opacity:.85;
}
@keyframes meteor-fall{
  0%{
    transform:translate3d(0,0,0) rotate(38deg);
    opacity:0;
  }
  5%{opacity:1;}
  55%{opacity:.85;}
  100%{
    /* 沿 38° 方向位移：dy = dx * tan(38°) ≈ 0.781 */
    transform:translate3d(var(--dx), calc(var(--dx) * 0.781), 0) rotate(38deg);
    opacity:0;
  }
}

/* 尊重系统「减少动态效果」设置 */
@media (prefers-reduced-motion: reduce){
  .meteor-field{display:none;}
}
"""

_MARKDOWN = """
.card-head{display:flex;align-items:baseline;gap:10px;
  padding-bottom:11px;margin-bottom:13px;border-bottom:1px solid var(--line);}
.card-title{font-size:.9rem;font-weight:600;color:var(--ink-1);}
.card-hint{margin-left:auto;font-size:.7rem;color:var(--ink-3);}
.card-hint.warn{color:var(--gold);}

.stMarkdown h3{
  font-size:.68rem;font-weight:600;letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink-3);margin:20px 0 9px;padding-bottom:7px;
  border-bottom:1px solid var(--line);
}
.stMarkdown h3:first-child{margin-top:0;}
.stMarkdown p{font-size:.88rem;line-height:1.78;color:var(--ink-2);}
.stMarkdown strong{color:var(--ink-1);font-weight:600;}
.stMarkdown ul{margin:7px 0 0;padding-left:1.15rem;}
.stMarkdown li{font-size:.88rem;line-height:1.78;color:var(--ink-2);margin-bottom:5px;}
.stMarkdown blockquote{
  border-left:2px solid rgba(124,140,255,.5);background:rgba(124,140,255,.06);
  margin:12px 0;padding:10px 14px;border-radius:0 var(--radius-sm) var(--radius-sm) 0;
  color:var(--ink-2);font-size:.85rem;
}
.stMarkdown code{
  background:rgba(255,255,255,.06);border:1px solid var(--line);
  border-radius:5px;padding:1px 5px;font-family:var(--mono);font-size:.82em;
  color:#c3caff;
}
.stMarkdown pre{
  background:#0b0f16;border:1px solid var(--line);border-radius:var(--radius-sm);
  padding:12px 14px;
}

.empty-state{padding:28px 10px;text-align:center;color:var(--ink-3);
  font-size:.84rem;line-height:1.9;}
.manage-sep{height:1px;background:var(--line);margin:12px 0;}
.stat-row{display:flex;justify-content:space-between;
  padding:8px 0;border-bottom:1px solid var(--grid);
  font-size:.8rem;color:var(--ink-2);}
.stat-row:last-child{border-bottom:none;}
.stat-row b{color:var(--ink-1);font-weight:500;font-variant-numeric:tabular-nums;}
"""


def apply_custom_css():
    """注入设计 token 与组件样式（整页只调用一次）"""
    st.markdown(
        f"<style>{_TOKENS}{_BASE}{_WIDGETS}{_COMPONENTS}{_METEOR}{_MARKDOWN}</style>",
        unsafe_allow_html=True,
    )
