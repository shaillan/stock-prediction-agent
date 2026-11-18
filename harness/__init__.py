# -*- coding: utf-8 -*-
"""Harness：Agent 运行时层（工具注册 / 预算守卫 / 轨迹 / 评测）

与 agent/（工作流）、agent_mode/（ReAct 循环的薄壳）的分工：
- harness 只负责「模型怎么被驱动」：工具怎么注册、循环怎么受控、
  每次运行留下什么证据、怎么回放打分。
- 业务能力（行情/财务/新闻/公告）仍留在 data/ 与 rag/，harness 不碰数据源。

三条边界（对应 README 的「缺口诚实」哲学）：
1. 事件是唯一真相：循环只产事件，CLI / UI / 评测都是消费者
2. 预算由代码兜底：步数 / token / 墙钟 / 成本都是硬约束，不靠模型自觉
3. 轨迹脱敏后才能落盘：写 JSONL 前统一过 mask，密钥不出机器
"""
__all__ = ["Budget", "BudgetExceeded", "Tracer"]


def __getattr__(name):
    # 延迟导出：只 import harness.types 的调用方不该顺带拉起 config 和 loguru
    if name == "Budget" or name == "BudgetExceeded":
        from harness.budget import Budget, BudgetExceeded
        return {"Budget": Budget, "BudgetExceeded": BudgetExceeded}[name]
    if name == "Tracer":
        from harness.trace import Tracer
        return Tracer
    raise AttributeError(name)
