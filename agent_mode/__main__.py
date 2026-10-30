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
    args = parser.parse_args()

    from agent_mode.loop import DEFAULT_MAX_STEPS, run_agent_mode
    from utils.llm_factory import create_chat_model

    kwargs = {}
    if args.model:
        # create_chat_model 的形参叫 model，不是 model_name——写错会在传 --model 时
        # 直接 TypeError，而默认路径（不传）永远发现不了
        kwargs["model"] = args.model
    llm = create_chat_model(**kwargs)

    print(f"\n🤖 Agent 模式（上限 {args.max_steps or DEFAULT_MAX_STEPS} 轮工具）")
    print(f"❓ {args.question}\n")

    result = run_agent_mode(
        question=args.question,
        stock_code=args.code,
        max_steps=args.max_steps or DEFAULT_MAX_STEPS,
        llm=llm,
    )

    print("\n" + "=" * 60)
    print("🧭 调用轨迹")
    print("=" * 60)
    for t in result["trajectory"]:
        arg_text = str(t["args"]) if args.show_args else ""
        print(f"  {t['step']:>2}. {t['tool']}  {arg_text}")
        print(f"      → {t['summary']}")

    print("\n" + "=" * 60)
    print("💬 回答" + ("（步数到顶强制收尾）" if result["stopped"] == "cap" else ""))
    print("=" * 60)
    print(result["answer"])
    print(f"\n（共 {result['steps_used']} 次工具调用）")


if __name__ == "__main__":
    main()
