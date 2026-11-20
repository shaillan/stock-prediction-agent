"""背景流星雨特效 —— 纯 CSS 实现（不依赖 JS，不会被 Streamlit 的 HTML 清洗拦掉）

设计要点
--------
1. **不遮挡内容**：整层 `position:fixed; z-index:-1; pointer-events:none`，
   落在 `[data-testid="stMain"]` 这个 isolation 层的最底部 —— 在页面渐变背景之上、
   所有正文之下。既看得见，又永远点不到、选不中、盖不住字。
2. **和 Aurora 极光风格协调**：流星色只取冷色系（白 / 淡蓝 / 青），
   与 --accent(#7c8cff) / --accent-2(#22d3ee) 同族；亮度压得很低（0.35~0.9），
   在 #070a0f 的深底上像远处的星屑，而不是舞台追光。
3. **性能**：只用 transform / opacity 两个合成属性做动画，不触发重排；
   元素数量固定（22 颗流星 + 40 颗星点），随机参数在服务端算好写进 inline style，
   所以每次 rerun 的星图是稳定的，不会闪。
4. **无障碍**：`prefers-reduced-motion: reduce` 时整层隐藏。
"""
import math
import random

import streamlit as st

# 流星尾迹的倾斜角（度）。所有流星同向，才像同一片天空。
_ANGLE = 38.0


def _build_meteors(count: int = 30, seed: int = 20261120) -> str:
    """生成流星元素。参数固定 seed，保证每次 rerun 星图一致。"""
    rnd = random.Random(seed)
    colors = ["#ffffff", "#d6e4ff", "#a9c8ff", "#9ff0ff", "#c3caff"]
    parts = []
    for _ in range(count):
        # 起点铺满整个视口并向外扩一圈，避免流星"凭空出现在画面中间"
        x = rnd.uniform(-25, 105)
        y = rnd.uniform(-35, 55)
        length = rnd.uniform(110, 260)         # 尾迹长度 px
        thick = rnd.choice([1.2, 1.5, 1.5, 2.0, 2.4])
        dur = rnd.uniform(4.5, 11.0)           # 单次划过耗时
        delay = rnd.uniform(0, 15)             # 错峰，避免齐刷刷一起飞
        travel = rnd.uniform(95, 165)          # 沿自身轴向的位移（vw）
        color = rnd.choice(colors)
        parts.append(
            f'<i class="m" style="--x:{x:.2f}vw;--y:{y:.2f}vh;--len:{length:.0f}px;'
            f'--th:{thick}px;--dur:{dur:.2f}s;--delay:{delay:.2f}s;'
            f'--dx:{travel:.0f}vw;--c:{color}"></i>'
        )
    return "".join(parts)


def _build_stars(count: int = 40, seed: int = 7) -> str:
    """背景星点：给流星雨一点"深空"的底噪，让画面不空。"""
    rnd = random.Random(seed)
    parts = []
    for _ in range(count):
        x = rnd.uniform(0, 100)
        y = rnd.uniform(0, 100)
        size = rnd.choice([1, 1, 1.5, 2])
        dur = rnd.uniform(2.6, 7.5)
        delay = rnd.uniform(0, 8)
        op = rnd.uniform(0.28, 0.75)
        parts.append(
            f'<i class="s" style="--x:{x:.2f}vw;--y:{y:.2f}vh;--sz:{size}px;'
            f'--d:{dur:.2f}s;--dl:{delay:.2f}s;--o:{op:.2f}"></i>'
        )
    return "".join(parts)


def render_meteor_shower(enabled: bool = True) -> None:
    """把流星雨背景层挂到页面上（整页调用一次即可）。

    Args:
        enabled: 为 False 时**完全不渲染**这一层 —— 流星、星点、极光雾一起消失，
                 页面回到 `.stApp::before` 的纯极光渐变背景。
                 不渲染（而不是用 CSS 隐藏）的好处：关掉后连动画帧都不再跑，
                 零 CPU 开销，也不会有任何残留层参与层叠。
    """
    if not enabled:
        return

    html = (
        '<div class="meteor-field" aria-hidden="true">'
        '<div class="meteor-nebula"></div>'
        f"{_build_stars()}"
        f"{_build_meteors()}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
