"""自定义 Streamlit CSS —— 专业金融终端风（深色）

设计 token 与 design/ui_mockup.html 一一对应，改色请两处一起改。
配色经过校验：涨 #e66767 / 跌 #199e70 在 #11151c 上分别为 5.66:1、5.37:1；
两者色盲区分度 ΔE 6.5 属警告带，所以任何涨跌色**必须**同时带 ▲▼ 或正负号。
"""
import streamlit as st

_TOKENS = """
:root{
  --page:#0a0c10;
  --surface-1:#11151c;
  --surface-2:#161b24;
  --surface-3:#1c2330;
  --line:#232a36;
  --grid:#1b212b;
  --ink-1:#e8edf5;
  --ink-2:#a7b1c2;
  --ink-3:#8a94a6;
  --up:#e66767;
  --down:#199e70;
  --accent:#e0a33a;
  --focus:#3987e5;
  --mono:"SFMono-Regular",Consolas,"Liberation Mono",monospace;
}
"""

_BASE = """
.stApp{background:var(--page);color:var(--ink-1);}
[data-testid="stHeader"]{background:transparent;}
/* 只能藏工具栏里的「动作」（Deploy / ⋮ 菜单），**不能**整条 stToolbar 一起 display:none：
   侧边栏收起后的「展开」箭头 stExpandSidebarButton 也长在这条工具栏里，
   整条藏掉的话侧边栏一旦收起，左上角就什么都不剩，再也打不开了。
   （另：别给 stHeader 设 height:0 之类的，Streamlit 自己的 header 规则优先级更高，
     写了也不生效，只会在升级后变成隐患。） */
[data-testid="stToolbarActions"],
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"]{display:none;}
#MainMenu,footer{visibility:hidden;}
.block-container{padding-top:1.4rem;padding-bottom:3rem;max-width:1440px;}
[data-testid="stSidebar"]{
  background:var(--surface-1);border-right:1px solid var(--line);
}
[data-testid="stSidebar"] .block-container,
[data-testid="stSidebarUserContent"]{padding-top:1.2rem;}
[data-testid="stSidebar"] hr{border-color:var(--line);margin:.6rem 0;}
/* 侧边栏分区标题：和正文的卡片标签同一套语气，不要用大号 h2 抢戏 */
[data-testid="stSidebar"] h2{
  font-size:.7rem;font-weight:500;letter-spacing:.12em;color:var(--ink-3);
  margin:14px 0 8px;padding-bottom:7px;border-bottom:1px solid var(--line);
}
h1,h2,h3,h4{color:var(--ink-1);letter-spacing:.01em;}
h1{font-size:1.45rem;font-weight:600;}
h2{font-size:1.15rem;font-weight:600;}
h3{font-size:1rem;font-weight:600;}
p,li,.stMarkdown{color:var(--ink-2);}
a{color:var(--focus);}
[data-testid="stCaptionContainer"],.stCaption{color:var(--ink-3);}
[data-testid="stCaptionContainer"] p,.stCaption p{color:inherit!important;}
hr{border-color:var(--line);}
"""

_WIDGETS = """
/* 按钮 */
.stButton>button, .stDownloadButton>button{
  border-radius:8px;border:1px solid var(--line);
  background:var(--surface-2);color:var(--ink-1);
  font-size:.86rem;padding:.42rem .9rem;transition:.15s;
}
.stButton>button:hover, .stDownloadButton>button:hover{
  background:var(--surface-3);border-color:#2f3849;color:var(--ink-1);
}
.stButton>button[kind="primary"]{
  background:var(--accent);border-color:var(--accent);color:#151006;font-weight:600;
}
.stButton>button[kind="primary"]:hover{
  background:#eab04a;border-color:#eab04a;color:#151006;
}
.stButton>button:disabled{opacity:.45;}
/* 按钮里的文字是 <p>，会被全局 p{color:--ink-2} 盖成浅灰（主按钮上就是白字配黄底），
   这里强制回继承按钮自身的颜色 */
.stButton>button p,.stDownloadButton>button p,.stFormSubmitButton>button p{
  color:inherit!important;
}
.stFormSubmitButton>button{border-radius:8px;}

/* 输入控件 */
.stTextInput input,.stNumberInput input,.stDateInput input{
  background:var(--surface-2)!important;color:var(--ink-1)!important;
  border:1px solid var(--line)!important;border-radius:8px!important;
}
.stTextInput input:focus,.stNumberInput input:focus{
  border-color:#3a465c!important;box-shadow:none!important;
}
div[data-baseweb="select"]>div{
  background:var(--surface-2)!important;border-color:var(--line)!important;
  border-radius:8px!important;color:var(--ink-1)!important;
}
div[data-baseweb="popover"] ul{background:var(--surface-2)!important;}
label,.stRadio label,.stCheckbox label{color:var(--ink-2)!important;}

/* 展开器 */
[data-testid="stExpander"] details{
  background:var(--surface-1);border:1px solid var(--line)!important;
  border-radius:10px!important;
}
[data-testid="stExpander"] summary{color:var(--ink-2);font-size:.86rem;}

/* 标签页 */
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"]{
  background:transparent;color:var(--ink-3);border-radius:7px 7px 0 0;
  padding:.45rem .85rem;font-size:.86rem;
}
.stTabs [aria-selected="true"]{background:var(--surface-2);color:var(--ink-1);}
.stTabs [data-baseweb="tab-highlight"]{background:var(--accent);}

/* 进度条 */
.stProgress>div>div>div>div{background:var(--accent);}

/* 提示框：默认会刷一层 20% 的品牌蓝，深色页上就是一块亮蓝。
   改成实心面板 + 左侧强调条区分 info/success/warning/error */
[data-testid="stAlert"]{
  background:var(--surface-1);border:1px solid var(--line);
  border-left-width:3px;border-radius:8px;color:var(--ink-2);
}
[data-testid="stAlertContainer"]{background:transparent!important;}
[data-testid="stAlert"]:has([data-testid*="ContentInfo"]){border-left-color:var(--focus);}
[data-testid="stAlert"]:has([data-testid*="ContentSuccess"]){border-left-color:var(--down);}
[data-testid="stAlert"]:has([data-testid*="ContentWarning"]){border-left-color:var(--accent);}
[data-testid="stAlert"]:has([data-testid*="ContentError"]){border-left-color:var(--up);}
[data-testid="stNotification"]{background:var(--surface-2);}

/* 边框容器 = 卡片 */
[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--surface-1);border:1px solid var(--line)!important;
  border-radius:10px;
}

/* 弹窗（st.dialog）：默认是半透明灰，和深色页面糊在一起，改成实心面板 */
div[role="dialog"]{
  background:var(--surface-1)!important;
  border:1px solid #2c3544;border-radius:14px;
  box-shadow:0 30px 80px rgba(0,0,0,.6);
}
"""

_COMPONENTS = """
/* 页面标题区 */
.term-topbar{
  display:flex;align-items:flex-end;gap:14px;
  padding:0 0 14px;margin-bottom:16px;
  border-bottom:1px solid var(--line);
}
.term-topbar h1{margin:0;font-size:1.4rem;font-weight:600;}
.term-topbar .sub{margin:5px 0 0;font-size:.78rem;color:var(--ink-3);}
.term-badge{
  margin-left:auto;display:inline-flex;align-items:center;gap:6px;
  font-size:.72rem;color:var(--ink-2);border:1px solid var(--line);
  border-radius:999px;padding:3px 10px;background:var(--surface-1);
}
.term-badge .live{width:6px;height:6px;border-radius:50%;background:var(--down);}

/* 行情条 */
.quote-strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;}
.quote-card{
  background:var(--surface-1);border:1px solid var(--line);
  border-radius:10px;padding:12px 14px;
}
.quote-top{display:flex;align-items:baseline;gap:8px;}
.quote-name{font-weight:600;font-size:.86rem;color:var(--ink-1);}
.quote-code{font:.7rem/1 var(--mono);color:var(--ink-3);}
.quote-badge{margin-left:auto;font-size:.66rem;color:var(--ink-3);
  border:1px solid var(--line);border-radius:4px;padding:1px 5px;}
.quote-price-row{display:flex;align-items:baseline;gap:9px;margin-top:4px;}
.quote-price{font-size:1.45rem;font-weight:600;letter-spacing:-.01em;color:var(--ink-1);}
.quote-meta{font-size:.72rem;color:var(--ink-3);margin-top:2px;
  font-variant-numeric:tabular-nums;}
.delta{font-size:.78rem;font-weight:600;font-variant-numeric:tabular-nums;}
.delta.up{color:var(--up);}
.delta.down{color:var(--down);}
.delta.flat{color:var(--ink-2);}
.quote-empty{color:var(--ink-3);font-size:.78rem;margin-top:8px;}

/* 卡片内的分区标题 */
.section-label{
  display:flex;align-items:center;gap:8px;
  font-size:.66rem;letter-spacing:.14em;color:var(--ink-3);
  text-transform:uppercase;margin:18px 0 8px;
}
.section-label::after{content:"";flex:1;height:1px;background:var(--line);}
.section-label:first-child{margin-top:0;}
.lead{font-size:.95rem;color:var(--ink-1);line-height:1.7;}
.prose{font-size:.88rem;color:var(--ink-2);line-height:1.8;}
.prose strong{color:var(--ink-1);}

/* 事件时间线 */
.tl{list-style:none;margin:0;padding:0;}
.tl-item{display:grid;grid-template-columns:9px 1fr;gap:10px;
  padding-bottom:13px;position:relative;}
.tl-item:last-child{padding-bottom:0;}
.tl-item::before{content:"";position:absolute;left:4px;top:11px;bottom:0;
  width:1px;background:var(--line);}
.tl-item:last-child::before{display:none;}
.tl-dot{width:9px;height:9px;border-radius:50%;background:var(--surface-3);
  border:1px solid var(--line);margin-top:4px;}
.tl-dot.hot{background:var(--accent);border-color:var(--accent);}
.tl-date{font:.66rem/1.6 var(--mono);color:var(--ink-3);}
.tl-title{font-size:.8rem;color:var(--ink-1);line-height:1.5;}
.tl-src{font-size:.7rem;color:var(--ink-3);margin-top:1px;}

/* KPI */
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;}
.kpi{background:var(--surface-1);border:1px solid var(--line);
  border-radius:10px;padding:12px 14px;}
.kpi-label{font-size:.72rem;color:var(--ink-3);}
.kpi-value{font-size:1.3rem;font-weight:600;margin-top:3px;color:var(--ink-1);}
.kpi-note{font-size:.7rem;color:var(--ink-3);margin-top:2px;}
/* 沿用 A 股约定：正/多在红、负/空在绿，和行情条的 .delta 保持一致。
   只染数值本身，注释行保持中性——注释常是参照值（MA20、零轴位置），染色会被误读成涨跌 */
.kpi-value.up{color:var(--up);}
.kpi-value.down{color:var(--down);}

/* 套餐卡 */
.plan-card{background:var(--surface-2);border:1px solid var(--line);
  border-radius:10px;padding:12px 14px;}
.plan-row{display:flex;justify-content:space-between;align-items:baseline;
  font-size:.78rem;color:var(--ink-2);}
.plan-name{color:var(--accent);font-weight:600;}
.plan-usage{font:.7rem/1 var(--mono);color:var(--ink-3);}

/* 免责 */
.disclaimer{border-top:1px solid var(--line);padding-top:10px;margin-top:14px;
  font-size:.72rem;color:var(--ink-3);line-height:1.65;}
.disclaimer b{color:var(--ink-2);font-weight:500;}

/* 兼容旧组件（预测卡/指标卡/步骤条） */
.main-header{font-size:1.45rem;font-weight:600;color:var(--ink-1);margin:0;}
.prediction-card{border-radius:10px;padding:1.1rem;margin:.6rem 0;
  border:1px solid var(--line);background:var(--surface-1);border-left-width:3px;}
.prediction-bullish{border-left-color:var(--up);}
.prediction-bearish{border-left-color:var(--down);}
.prediction-neutral{border-left-color:var(--accent);}
.metric-card{text-align:center;padding:.9rem;border-radius:10px;
  background:var(--surface-1);border:1px solid var(--line);}
.metric-value{font-size:1.3rem;font-weight:600;color:var(--ink-1);}
.metric-label{font-size:.75rem;color:var(--ink-3);}
.metric-up{color:var(--up);}
.metric-down{color:var(--down);}
.metric-warn{color:var(--accent);}
.metric-value.up{color:var(--up);}
.metric-value.down{color:var(--down);}
.metric-value.warn{color:var(--accent);}

/* 目标价位区间条：绿(支撑) → 线灰 → 红(压力)，中间一根竖线标现价 */
.range-bar{position:relative;height:6px;border-radius:3px;margin:26px 0 4px;
  background:linear-gradient(to right,var(--down),#3a4354 50%,var(--up));}
.range-mark{position:absolute;top:-20px;transform:translateX(-50%);
  white-space:nowrap;font-size:.72rem;color:var(--ink-1);}
.range-mark::after{content:"";display:block;width:2px;height:12px;margin:2px auto 0;
  background:var(--ink-1);border-radius:1px;}
.step-dot{width:26px;height:26px;border-radius:50%;display:inline-block;
  line-height:26px;font-size:.72rem;font-weight:700;text-align:center;}
.step-dot-active{background:var(--accent);color:#151006;}
.step-dot-done{background:var(--down);color:#04110c;}
.step-dot-pending{background:var(--surface-3);color:var(--ink-3);}
.step-label{font-size:.72rem;color:var(--ink-3);margin-top:4px;text-align:center;}
.risk-warning{background:var(--surface-1);border:1px solid var(--line);
  border-left:3px solid var(--accent);border-radius:8px;padding:.9rem;margin-top:1rem;}
"""

_MARKDOWN = """
/* 卡片头部：标题 + 右侧提示 */
.card-head{display:flex;align-items:baseline;gap:10px;
  padding-bottom:10px;margin-bottom:12px;border-bottom:1px solid var(--line);}
.card-title{font-size:.9rem;font-weight:600;color:var(--ink-1);}
.card-hint{margin-left:auto;font-size:.7rem;color:var(--ink-3);}
.card-hint.warn{color:var(--accent);}

/* 模型输出的三段式小标题（### 一句话 / 发生了什么 / 值得留意） */
.stMarkdown h3{
  font-size:.68rem;font-weight:500;letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink-3);margin:18px 0 8px;padding-bottom:6px;
  border-bottom:1px solid var(--line);
}
.stMarkdown h3:first-child{margin-top:0;}
.stMarkdown p{font-size:.88rem;line-height:1.75;color:var(--ink-2);}
.stMarkdown strong{color:var(--ink-1);font-weight:600;}
.stMarkdown ul{margin:6px 0 0;padding-left:1.1rem;}
.stMarkdown li{font-size:.88rem;line-height:1.75;color:var(--ink-2);margin-bottom:4px;}

/* 套餐进度条 / 空状态 / 素材统计 */
.plan-bar{height:4px;border-radius:2px;background:var(--surface-3);
  margin-top:8px;overflow:hidden;}
.plan-bar>i{display:block;height:100%;background:var(--accent);border-radius:2px;}
.empty-state{padding:26px 8px;text-align:center;color:var(--ink-3);
  font-size:.84rem;line-height:1.9;}
.manage-sep{height:1px;background:var(--line);margin:10px 0;}
.stat-row{display:flex;justify-content:space-between;
  padding:7px 0;border-bottom:1px solid var(--grid);
  font-size:.8rem;color:var(--ink-2);}
.stat-row:last-child{border-bottom:none;}
.stat-row b{color:var(--ink-1);font-weight:500;font-variant-numeric:tabular-nums;}
"""


def apply_custom_css():
    """注入设计 token 与组件样式（整页只调用一次）"""
    st.markdown(
        f"<style>{_TOKENS}{_BASE}{_WIDGETS}{_COMPONENTS}{_MARKDOWN}</style>",
        unsafe_allow_html=True,
    )
