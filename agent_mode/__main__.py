# -*- coding: utf-8 -*-
"""Agent 模式 CLI：python -m agent_mode "600519 最近走势如何" --code 600519"""
import argparse
import sys

from loguru import logger


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows GBK 控制台防乱码

    parser = argparse.ArgumentParser(
        prog="python -m agent_mode",
        description="Agent 模式：LLM 自主调工具回答开放式问题（实验功能）",
    )
    parser.add_argument("question", help="开放式问题，如 '600519 最近走势如何'")
    parser.add_argument("--code", default="", help="默认研究对象（股票代码，如 600519）")
    parser.add_argument("--max-steps", type=int, default=None, help="工具轮数上限（默认 12）")
    parser.add_argument("--model", default=None, help="覆盖 config 里的模型名")
    parser.add_argument("--show-args", action="store_true", help="轨迹里显示完整工具参数")
    parser.add_argument("--no-trace", action="store_true",
                        help="不落轨迹（默认写入 runs/<日期>/<run_id>.jsonl，已脱敏）")
    parser.add_argument("--max-tokens", type=int, default=None,
                        help="单次问答 token 预算（默认取 config）")
    parser.add_argument("--max-seconds", type=float, default=None,
                        help="单次问答墙钟预算，秒（默认取 config）")
    args = parser.parse_args()

    from agent_mode.loop import DEFAULT_MAX_STEPS, run_agent_mode
    from harness.budget import from_settings
    from harness.trace import Tracer
    from utils.llm_factory import create_chat_model

    kwargs = {}
    if args.model:
        # create_chat_model 的形参叫 model，不是 model_name——写错会在传 --model 时
        # 直接 TypeError，而默认路径（不传）永远发现不了
        kwargs["model"] = args.model
    llm = create_chat_model(**kwargs)

    max_steps = args.max_steps or DEFAULT_MAX_STEPS
    budget = from_settings(max_steps, max_tokens=args.max_tokens,
                           max_seconds=args.max_seconds)
    tracer = None
    if not args.no_trace:
        tracer = Tracer(question=args.question, stock_code=args.code,
                        model=getattr(llm, "model_name", "") or args.model or "")

    print(f"\n🤖 Agent 模式（上限 {max_steps} 轮工具 / "
          f"{budget.max_seconds:.0f}s / {budget.max_tokens} tokens）")
    print(f"❓ {args.question}\n")

    result = run_agent_mode(
        question=args.question,
        stock_code=args.code,
        max_steps=max_steps,
        llm=llm,
        budget=budget,
        tracer=tracer,
    )

    print("\n" + "=" * 60)
    print("🧭 调用轨迹")
    print("=" * 60)
    for t in result["trajectory"]:
        arg_text = str(t["args"]) if args.show_args else ""
        print(f"  {t['step']:>2}. {t['tool']}  {arg_text}")
        print(f"      → {t['summary']}")

    suffix = {"cap": "（步数到顶强制收尾）",
              "budget": f"（预算触顶：{result.get('budget_reason')}）"}.get(
        result["stopped"], "")
    print("\n" + "=" * 60)
    print("💬 回答" + suffix)
    print("=" * 60)
    print(result["answer"])

    usage = result.get("usage") or {}
    print(f"\n（共 {result['steps_used']} 次工具调用，"
          f"耗时 {usage.get('elapsed_s', 0):.1f}s，"
          f"token {usage.get('total_tokens', 0)}）")
    cost = usage.get("cost_cny")
    print("（成本未配置：在 config.py 填 harness_price_* 后会显示）"
          if cost is None else f"（预估成本 ¥{cost:.4f}）")
    if result.get("trace_path"):
        print(f"📄 轨迹已存：{result['trace_path']}")


if __name__ == "__main__":
    main()
