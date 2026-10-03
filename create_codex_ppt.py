"""
生成一份关于 OpenAI Codex 的专业 PPT
适合场景：刚下载 Codex，需要在短时间内做一份相关汇报
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

# ── 颜色方案 ──────────────────────────────────────────────
BG_DARK   = RGBColor(0x1A, 0x1A, 0x2E)   # 深邃海军蓝背景
ACCENT    = RGBColor(0x00, 0xD2, 0xFF)   # 青色强调
ACCENT2   = RGBColor(0x7B, 0x2F, 0xFF)   # 紫色渐变
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT     = RGBColor(0xCC, 0xCC, 0xDD)
GREEN     = RGBColor(0x00, 0xE6, 0x76)
ORANGE    = RGBColor(0xFF, 0x9F, 0x43)
CARD_BG   = RGBColor(0x22, 0x22, 0x3E)   # 卡片背景

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)

# ── 辅助函数 ──────────────────────────────────────────────
def add_bg(slide, color=BG_DARK):
    """填充纯色背景"""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color

def add_shape_bg(slide, left, top, width, height, color=CARD_BG, radius=None):
    """添加一个圆角矩形作为卡片"""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()  # 无边框
    if radius is not None:
        shape.adjustments[0] = radius
    return shape

def add_text_box(slide, left, top, width, height, text, font_size=18,
                 color=WHITE, bold=False, alignment=PP_ALIGN.LEFT, font_name="Microsoft YaHei"):
    """添加文本框"""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = alignment
    return txBox

def add_bullet_frame(slide, left, top, width, height, items, font_size=16,
                     color=LIGHT, bullet_color=ACCENT, font_name="Microsoft YaHei"):
    """添加带要点的文本框"""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = item
        p.font.size = Pt(font_size)
        p.font.color.rgb = color
        p.font.name = font_name
        p.space_after = Pt(10)
        p.level = 0
    return txBox

def add_accent_bar(slide, left, top, width, height, color=ACCENT):
    """添加装饰性色条"""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left, top, width, height
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape

def add_circle_deco(slide, left, top, size, color=ACCENT):
    """添加装饰圆点"""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, left, top, size, size
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape

# ═══════════════════════════════════════════════════════════
# Slide 1 — 封面
# ═══════════════════════════════════════════════════════════
slide1 = prs.slides.add_slide(prs.slide_layouts[6])  # blank
add_bg(slide1)

# 顶部装饰条
add_accent_bar(slide1, Inches(0), Inches(0), prs.slide_width, Inches(0.06))

# 左侧大装饰圆
add_circle_deco(slide1, Inches(0.8), Inches(1.5), Inches(1.2), ACCENT)
add_circle_deco(slide1, Inches(10.5), Inches(5.0), Inches(0.8), ACCENT2)

# 主标题
add_text_box(slide1, Inches(1.5), Inches(2.2), Inches(10), Inches(1.2),
             "OpenAI Codex", font_size=60, color=WHITE, bold=True)

# 副标题
add_text_box(slide1, Inches(1.5), Inches(3.5), Inches(10), Inches(0.8),
             "从下载到入门：AI 代码生成初探", font_size=28, color=ACCENT)

# 分割线
add_accent_bar(slide1, Inches(1.5), Inches(4.5), Inches(2.5), Inches(0.04), ACCENT)

# 信息
add_text_box(slide1, Inches(1.5), Inches(4.8), Inches(10), Inches(0.6),
             "汇报人：叶树峰  |  2026年7月", font_size=18, color=LIGHT)

# ═══════════════════════════════════════════════════════════
# Slide 2 — 目录
# ═══════════════════════════════════════════════════════════
slide2 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide2)
add_shape_bg(slide2, Inches(0.5), Inches(0.3), Inches(12.3), Inches(6.9), CARD_BG)
add_accent_bar(slide2, Inches(0.5), Inches(0.3), Inches(12.3), Inches(0.06), ACCENT)

add_text_box(slide2, Inches(1.2), Inches(0.8), Inches(5), Inches(0.8),
             "📋 目录", font_size=36, color=WHITE, bold=True)

toc_items = [
    ("01", "什么是 Codex —— 概念与背景"),
    ("02", "核心能力 —— Codex 能做什么"),
    ("03", "下载与安装 —— 我的实践记录"),
    ("04", "基本使用 —— 从第一个请求开始"),
    ("05", "应用场景 —— 实际工作流中的 Codex"),
    ("06", "学习路线 —— 后续规划"),
]
for i, (num, title) in enumerate(toc_items):
    y = Inches(2.0) + Inches(i * 0.8)
    # 数字
    add_text_box(slide2, Inches(1.5), y, Inches(0.8), Inches(0.6),
                 num, font_size=24, color=ACCENT, bold=True)
    # 分隔
    add_accent_bar(slide2, Inches(2.3), y + Inches(0.28), Inches(0.3), Inches(0.03), ACCENT)
    # 标题
    add_text_box(slide2, Inches(2.8), y, Inches(8), Inches(0.6),
                 title, font_size=22, color=LIGHT)

# ═══════════════════════════════════════════════════════════
# Slide 3 — 什么是 Codex
# ═══════════════════════════════════════════════════════════
slide3 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide3)
add_accent_bar(slide3, Inches(0), Inches(0), prs.slide_width, Inches(0.06))
add_text_box(slide3, Inches(1.0), Inches(0.5), Inches(10), Inches(0.8),
             "01  什么是 Codex", font_size=36, color=WHITE, bold=True)

# 左侧卡片 — 定义
card1 = add_shape_bg(slide3, Inches(0.8), Inches(1.6), Inches(5.8), Inches(2.6), CARD_BG)
add_text_box(slide3, Inches(1.2), Inches(1.8), Inches(5), Inches(0.5),
             "💡 定义", font_size=22, color=ACCENT, bold=True)
add_bullet_frame(slide3, Inches(1.2), Inches(2.4), Inches(5), Inches(1.6), [
    "OpenAI Codex 是基于 GPT 系列模型\n的代码生成 AI 系统",
    "能够将自然语言描述转换为\n可执行的程序代码",
    "支持 Python, JavaScript, Go,\nTypeScript, Ruby 等数十种语言",
    "GitHub Copilot 的早期底层引擎",
], font_size=15, color=LIGHT)

# 右侧卡片 — 背景
card2 = add_shape_bg(slide3, Inches(7.0), Inches(1.6), Inches(5.5), Inches(2.6), CARD_BG)
add_text_box(slide3, Inches(7.4), Inches(1.8), Inches(5), Inches(0.5),
             "📖 发展背景", font_size=22, color=ACCENT2, bold=True)
add_bullet_frame(slide3, Inches(7.4), Inches(2.4), Inches(5), Inches(1.6), [
    "2021年8月：OpenAI 发布 Codex 论文\n及 API 测试版",
    "基于 GPT-3 在 GitHub 公开代码上\n微调训练而成",
    "2023年后逐步融入 GPT-3.5/GPT-4\n模型中，不再单独提供",
    "目前通过 OpenAI API（gpt-4o,\ngpt-4-turbo）间接使用 Codex 能力",
], font_size=15, color=LIGHT)

# 底部卡片 — 关键特性
card3 = add_shape_bg(slide3, Inches(0.8), Inches(4.6), Inches(11.7), Inches(2.2), CARD_BG)
add_text_box(slide3, Inches(1.2), Inches(4.8), Inches(5), Inches(0.5),
             "🔑 关键特性", font_size=22, color=GREEN, bold=True)

# 四列特性
features = [
    ("🌐", "多语言支持", "Python, JS, Go,\nTS, Ruby, PHP..."),
    ("🧠", "自然语言理解", "用中文/英文描述\n需求即可生成代码"),
    ("🔧", "工具集成", "与 VS Code, Terminal,\nJupyter 无缝集成"),
    ("📚", "上下文感知", "理解项目结构，\n生成适配的代码"),
]
for i, (icon, title, desc) in enumerate(features):
    x = Inches(1.2) + Inches(i * 2.9)
    add_text_box(slide3, x, Inches(5.4), Inches(2.5), Inches(0.4),
                 f"{icon} {title}", font_size=16, color=WHITE, bold=True)
    add_text_box(slide3, x, Inches(5.9), Inches(2.5), Inches(0.8),
                 desc, font_size=13, color=LIGHT)

# ═══════════════════════════════════════════════════════════
# Slide 4 — 核心能力
# ═══════════════════════════════════════════════════════════
slide4 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide4)
add_accent_bar(slide4, Inches(0), Inches(0), prs.slide_width, Inches(0.06))
add_text_box(slide4, Inches(1.0), Inches(0.5), Inches(10), Inches(0.8),
             "02  核心能力 —— Codex 能做什么", font_size=36, color=WHITE, bold=True)

capabilities = [
    ("📝", "代码补全", "根据上下文和注释\n自动补全代码行或函数", ACCENT),
    ("🔄", "代码翻译", "将一种编程语言的代码\n翻译为另一种语言", ACCENT2),
    ("🐛", "Debug 辅助", "根据报错信息定位问题\n并提供修复建议", GREEN),
    ("📖", "代码解释", "用自然语言解释复杂\n代码段的功能和逻辑", ORANGE),
    ("✨", "代码生成", "从自然语言描述\n直接生成完整函数/类", ACCENT),
    ("🧪", "测试生成", "自动为现有代码\n生成单元测试用例", ACCENT2),
]

for i, (icon, title, desc, color) in enumerate(capabilities):
    col = i % 3
    row = i // 3
    x = Inches(0.8) + Inches(col * 4.1)
    y = Inches(1.6) + Inches(row * 2.8)

    card = add_shape_bg(slide4, x, y, Inches(3.8), Inches(2.4), CARD_BG)
    add_circle_deco(slide4, x + Inches(0.2), y + Inches(0.2), Inches(0.15), color)
    add_text_box(slide4, x + Inches(0.4), y + Inches(0.3), Inches(3), Inches(0.5),
                 f"{icon} {title}", font_size=20, color=color, bold=True)
    add_text_box(slide4, x + Inches(0.4), y + Inches(1.0), Inches(3), Inches(1.2),
                 desc, font_size=14, color=LIGHT)

# ═══════════════════════════════════════════════════════════
# Slide 5 — 下载与安装（实践记录）
# ═══════════════════════════════════════════════════════════
slide5 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide5)
add_accent_bar(slide5, Inches(0), Inches(0), prs.slide_width, Inches(0.06))
add_text_box(slide5, Inches(1.0), Inches(0.5), Inches(10), Inches(0.8),
             "03  下载与安装 —— 我的实践记录", font_size=36, color=WHITE, bold=True)

# 左侧：安装步骤
card_left = add_shape_bg(slide5, Inches(0.8), Inches(1.6), Inches(5.8), Inches(5.2), CARD_BG)
add_text_box(slide5, Inches(1.2), Inches(1.8), Inches(5), Inches(0.5),
             "📦 环境准备与安装", font_size=22, color=ACCENT, bold=True)

steps = [
    "Step 1: 注册 OpenAI 账号并获取 API Key",
    "",
    "Step 2: 安装 OpenAI Python SDK\n    pip install openai",
    "",
    "Step 3: 配置 API Key\n    export OPENAI_API_KEY=\"sk-...\"\n    或在代码中设置环境变量",
    "",
    "Step 4: 安装 VS Code 插件（可选）\n    GitHub Copilot / Cody 等扩展",
    "",
    "Step 5: 验证连接\n    运行一个简单的代码生成\n    请求测试连通性",
]
add_bullet_frame(slide5, Inches(1.2), Inches(2.5), Inches(5.2), Inches(4.2),
                 steps, font_size=14, color=LIGHT, bullet_color=ACCENT)

# 右侧：我的进展
card_right = add_shape_bg(slide5, Inches(7.0), Inches(1.6), Inches(5.5), Inches(5.2), CARD_BG)
add_text_box(slide5, Inches(7.4), Inches(1.8), Inches(5), Inches(0.5),
             "📊 当前进展", font_size=22, color=GREEN, bold=True)

# 进度条背景
progress_bg = add_shape_bg(slide5, Inches(7.4), Inches(2.8), Inches(4.8), Inches(0.4), RGBColor(0x33, 0x33, 0x55))
# 进度条填充 (约 30%)
progress_fill = add_shape_bg(slide5, Inches(7.4), Inches(2.8), Inches(1.5), Inches(0.4), GREEN)

add_text_box(slide5, Inches(7.4), Inches(3.4), Inches(5), Inches(0.4),
             "✅ 已完成：环境下载与安装", font_size=16, color=GREEN, bold=True)
add_text_box(slide5, Inches(7.4), Inches(3.8), Inches(5), Inches(0.4),
             "📋 进行中：API 调用测试", font_size=14, color=ORANGE)
add_text_box(slide5, Inches(7.4), Inches(4.2), Inches(5), Inches(0.4),
             "📋 待完成：实际项目集成", font_size=14, color=LIGHT)

# 分隔线
add_accent_bar(slide5, Inches(7.4), Inches(4.8), Inches(4.8), Inches(0.02), RGBColor(0x44, 0x44, 0x66))

add_text_box(slide5, Inches(7.4), Inches(5.0), Inches(5), Inches(0.4),
             "💻 已安装的 Python 包", font_size=16, color=ACCENT, bold=True)
add_bullet_frame(slide5, Inches(7.4), Inches(5.4), Inches(5), Inches(1.2), [
    "openai==2.41.0",
    "langchain-openai==0.3.35",
], font_size=13, color=LIGHT)

# ═══════════════════════════════════════════════════════════
# Slide 6 — 基本使用示例
# ═══════════════════════════════════════════════════════════
slide6 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide6)
add_accent_bar(slide6, Inches(0), Inches(0), prs.slide_width, Inches(0.06))
add_text_box(slide6, Inches(1.0), Inches(0.5), Inches(10), Inches(0.8),
             "04  基本使用 —— 从第一个请求开始", font_size=36, color=WHITE, bold=True)

# 左侧代码示例
card_code = add_shape_bg(slide6, Inches(0.8), Inches(1.5), Inches(7.2), Inches(5.4), CARD_BG)
add_text_box(slide6, Inches(1.2), Inches(1.7), Inches(5), Inches(0.5),
             "🐍 Python 调用示例", font_size=20, color=ACCENT, bold=True)

code_text = (
    "from openai import OpenAI\n\n"
    "client = OpenAI()  # 自动读取环境变量\n\n"
    "response = client.chat.completions.create(\n"
    '    model="gpt-4o",\n'
    '    messages=[\n'
    '        {"role": "system",\n'
    '         "content": "你是一个 Python 编程助手"},\n'
    '        {"role": "user",\n'
    '         "content": "写一个函数：计算股票\n'
    '                   的移动平均线 (SMA)"}\n'
    '    ],\n'
    '    temperature=0.2\n'
    ")\n\n"
    "code = response.choices[0].message.content\n"
    'print(code)  # 输出生成的 Python 代码'
)

# 代码块背景
code_bg = add_shape_bg(slide6, Inches(1.2), Inches(2.4), Inches(6.4), Inches(4.2),
                        RGBColor(0x0D, 0x0D, 0x1A))
add_text_box(slide6, Inches(1.5), Inches(2.5), Inches(5.8), Inches(4.0),
             code_text, font_size=11, color=GREEN, font_name="Consolas")

# 右侧说明
add_text_box(slide6, Inches(8.5), Inches(1.7), Inches(4.2), Inches(0.5),
             "🎯 关键参数说明", font_size=20, color=ACCENT2, bold=True)

params = [
    ("model", "使用的模型名称\n(gpt-4o, gpt-4-turbo 等)"),
    ("messages", "对话历史，包含\nsystem prompt 和 user input"),
    ("temperature", "控制随机性 (0-2)\n越低越确定"),
    ("max_tokens", "限制输出最大长度\n(可选)"),
]
for i, (param, desc) in enumerate(params):
    y = Inches(2.5) + Inches(i * 1.2)
    add_text_box(slide6, Inches(8.5), y, Inches(1.5), Inches(0.4),
                 param, font_size=15, color=ACCENT, bold=True, font_name="Consolas")
    add_text_box(slide6, Inches(10.2), y, Inches(2.5), Inches(1.0),
                 desc, font_size=13, color=LIGHT)

# ═══════════════════════════════════════════════════════════
# Slide 7 — 实际应用场景
# ═══════════════════════════════════════════════════════════
slide7 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide7)
add_accent_bar(slide7, Inches(0), Inches(0), prs.slide_width, Inches(0.06))
add_text_box(slide7, Inches(1.0), Inches(0.5), Inches(10), Inches(0.8),
             "05  应用场景 —— 实际工作流中的 Codex", font_size=36, color=WHITE, bold=True)

scenarios = [
    ("📈", "量化交易策略开发",
     ["生成技术指标计算函数 (SMA, RSI, MACD)",
      "编写回测框架核心逻辑",
      "创建数据可视化代码",
      "API 对接与数据清洗脚本"],
     ACCENT),
    ("🌐", "Web 应用开发",
     ["前后端接口快速搭建",
      "数据库 CRUD 代码生成",
      "表单验证与错误处理",
      "单元测试自动生成"],
     ACCENT2),
    ("🤖", "自动化脚本",
     ["文件批量处理与重命名",
      "定时任务与爬虫脚本",
      "日志分析与报表生成",
      "CI/CD 流水线脚本"],
     GREEN),
]

for i, (icon, title, items, color) in enumerate(scenarios):
    x = Inches(0.6) + Inches(i * 4.2)
    card = add_shape_bg(slide7, x, Inches(1.5), Inches(3.9), Inches(5.3), CARD_BG)
    add_text_box(slide7, x + Inches(0.3), Inches(1.7), Inches(3.3), Inches(0.5),
                 f"{icon} {title}", font_size=18, color=color, bold=True)
    add_accent_bar(slide7, x + Inches(0.3), Inches(2.3), Inches(1.5), Inches(0.03), color)
    add_bullet_frame(slide7, x + Inches(0.3), Inches(2.6), Inches(3.3), Inches(3.8),
                     items, font_size=14, color=LIGHT, bullet_color=color)

# ═══════════════════════════════════════════════════════════
# Slide 8 — 与现有项目的结合
# ═══════════════════════════════════════════════════════════
slide8 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide8)
add_accent_bar(slide8, Inches(0), Inches(0), prs.slide_width, Inches(0.06))
add_text_box(slide8, Inches(1.0), Inches(0.5), Inches(12), Inches(0.8),
             "🔗 Codex × 股票预测 Agent 项目", font_size=36, color=WHITE, bold=True)

add_text_box(slide8, Inches(1.0), Inches(1.3), Inches(11), Inches(0.5),
             "将 Codex / GPT-4o 的代码生成能力融入现有的 Stock Prediction Agent 项目",
             font_size=18, color=LIGHT)

# 三个集成方向
integrations = [
    ("策略生成引擎", ACCENT, [
        "用自然语言描述交易策略",
        "AI 自动生成 Python 策略代码",
        "内置回测验证逻辑",
    ]),
    ("数据分析助手", ACCENT2, [
        "自动生成数据探索代码",
        "智能特征工程建议",
        "可视化图表一键生成",
    ]),
    ("代码审查与优化", GREEN, [
        "自动化 Code Review",
        "性能优化建议",
        "Bug 定位与修复方案",
    ]),
]

for i, (title, color, items) in enumerate(integrations):
    x = Inches(0.8) + Inches(i * 4.1)
    card = add_shape_bg(slide8, x, Inches(2.1), Inches(3.8), Inches(3.2), CARD_BG)
    add_accent_bar(slide8, x, Inches(2.1), Inches(3.8), Inches(0.05), color)
    add_text_box(slide8, x + Inches(0.3), Inches(2.4), Inches(3.2), Inches(0.5),
                 f"0{i+1} {title}", font_size=18, color=color, bold=True)
    add_bullet_frame(slide8, x + Inches(0.3), Inches(3.0), Inches(3.2), Inches(2.0),
                     items, font_size=14, color=LIGHT, bullet_color=color)

# 架构示意
arch_card = add_shape_bg(slide8, Inches(0.8), Inches(5.6), Inches(11.7), Inches(1.3), CARD_BG)
add_text_box(slide8, Inches(1.2), Inches(5.7), Inches(11), Inches(0.4),
             "🏗️ 集成架构示意", font_size=18, color=ACCENT, bold=True)

arch_text = ("用户自然语言输入  →  OpenAI GPT-4o API (Codex)  →  生成策略代码  →  股票预测 Agent 执行  →  回测结果输出")
add_text_box(slide8, Inches(1.2), Inches(6.2), Inches(11), Inches(0.5),
             arch_text, font_size=15, color=LIGHT, font_name="Consolas")

# ═══════════════════════════════════════════════════════════
# Slide 9 — 学习路线
# ═══════════════════════════════════════════════════════════
slide9 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide9)
add_accent_bar(slide9, Inches(0), Inches(0), prs.slide_width, Inches(0.06))
add_text_box(slide9, Inches(1.0), Inches(0.5), Inches(10), Inches(0.8),
             "06  学习路线与后续规划", font_size=36, color=WHITE, bold=True)

# 时间线风格
phases = [
    ("第 1 周", "基础掌握", ACCENT, [
        "熟悉 OpenAI API 调用",
        "实践代码生成基础用例",
        "了解 Prompt Engineering",
    ]),
    ("第 2 周", "进阶应用", ACCENT2, [
        "Advanced Prompt 技巧",
        "Function Calling 机制",
        "流式输出 (Streaming)",
    ]),
    ("第 3 周", "项目集成", GREEN, [
        "将 Codex 集成到股票 Agent",
        "实现策略代码自动生成",
        "编写集成测试",
    ]),
    ("第 4 周", "优化与总结", ORANGE, [
        "性能优化与成本控制",
        "最佳实践文档整理",
        "团队分享与知识沉淀",
    ]),
]

for i, (time, title, color, items) in enumerate(phases):
    x = Inches(0.6) + Inches(i * 3.15)
    # 时间标签
    tag = add_shape_bg(slide9, x, Inches(1.5), Inches(2.8), Inches(0.5), color)
    add_text_box(slide9, x, Inches(1.52), Inches(2.8), Inches(0.45),
                 f"{time}：{title}", font_size=15, color=BG_DARK, bold=True, alignment=PP_ALIGN.CENTER)
    # 内容卡片
    card = add_shape_bg(slide9, x, Inches(2.2), Inches(2.8), Inches(3.8), CARD_BG)
    add_bullet_frame(slide9, x + Inches(0.2), Inches(2.4), Inches(2.4), Inches(3.4),
                     items, font_size=13, color=LIGHT, bullet_color=color)

# 底部目标
goal_card = add_shape_bg(slide9, Inches(0.8), Inches(6.3), Inches(11.7), Inches(0.7),
                         RGBColor(0x28, 0x28, 0x50))
add_accent_bar(slide9, Inches(0.8), Inches(6.3), Inches(0.06), Inches(0.7), GREEN)
add_text_box(slide9, Inches(1.2), Inches(6.35), Inches(11), Inches(0.55),
             "🎯 最终目标：将 AI 代码生成能力深度整合到股票预测工作流中，提升开发效率 3x+",
             font_size=18, color=GREEN, bold=True)

# ═══════════════════════════════════════════════════════════
# Slide 10 — 总结与展望
# ═══════════════════════════════════════════════════════════
slide10 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide10)
add_accent_bar(slide10, Inches(0), Inches(0), prs.slide_width, Inches(0.06))

# 大标题
add_text_box(slide10, Inches(1.5), Inches(1.5), Inches(10), Inches(1.0),
             "总结与展望", font_size=48, color=WHITE, bold=True, alignment=PP_ALIGN.CENTER)

add_accent_bar(slide10, Inches(5.0), Inches(2.5), Inches(3.3), Inches(0.05), ACCENT)

# 关键总结
summary_card = add_shape_bg(slide10, Inches(1.5), Inches(3.0), Inches(10.3), Inches(2.2), CARD_BG)

summary_items = [
    "✅ 已完成 Codex (OpenAI SDK) 的环境搭建与安装",
    "✅ 了解了 Codex 的核心能力与 API 调用方式",
    "📋 下一步：在股票预测 Agent 项目中实践集成",
    "💡 Codex + 领域知识 = 高效自动化开发",
]

for i, item in enumerate(summary_items):
    add_text_box(slide10, Inches(2.0), Inches(3.3) + Inches(i * 0.45), Inches(9.5), Inches(0.4),
                 item, font_size=17, color=LIGHT)

# 底部
add_text_box(slide10, Inches(1.5), Inches(5.8), Inches(10), Inches(0.6),
             "谢谢！", font_size=40, color=ACCENT, bold=True, alignment=PP_ALIGN.CENTER)
add_text_box(slide10, Inches(1.5), Inches(6.5), Inches(10), Inches(0.4),
             "Questions & Discussion", font_size=20, color=LIGHT, alignment=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════
# 保存
# ═══════════════════════════════════════════════════════════
output_path = os.path.join(os.path.dirname(__file__), "Codex_介绍与入门.pptx")
prs.save(output_path)
print(f"✅ PPT 已生成：{output_path}")
