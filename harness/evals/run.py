# -*- coding: utf-8 -*-
"""评测运行器：python -m harness.evals.run --suite smoke

用法:
    python -m harness.evals.run                    # 跑 smoke 全集
    python -m harness.evals.run --limit 3          # 只跑前 3 条（省钱）
    python -m harness.evals.run --case market      # 按 id 子串过滤
    python -m harness.evals.run --model deepseek-chat
    python -m harness.evals.run --no-trace         # 不落逐条轨迹

退出码：全部通过 0，有失败 1（方便以后接 CI）。
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.budget import from_settings
from harness.evals.scorers import check_case, load_suite
from harness.trace import Tracer

DEFAULT_SUITE = Path(__file__).parent / "suites" / "smoke.jsonl"
REPORT_DIR = Path("runs/evals")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Agent harness 评测")
    parser.add_argument("--suite", default=str(DEFAULT_SUITE), help="用例集 JSONL 路径")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条，0 表示全部")
    parser.add_argument("--case", default="", help="按 id 子串过滤，如 market")
    parser.add_argument("--model", default=None, help="覆盖 config 里的模型名")
    parser.add_argument("--max-steps", type=int, default=10, help="每条用例的步数上限")
    parser.add_argument("--no-trace", action="store_true", help="不落逐条轨迹")
    return parser.parse_args(argv)


def select_cases(cases, case_filter: str = "", limit: int = 0):
    if case_filter:
        cases = [c for c in cases if case_filter in str(c.get("id", ""))]
    if limit and limit > 0:
        cases = cases[:limit]
    return cases


def run_one(case: dict, llm, max_steps: int, use_trace: bool = True) -> dict:
    """跑一条用例并打分；异常由 main 捕获成失败，不中断整批"""
    from agent_mode.loop import run_agent_mode

    question = case.get("question", "")
    code = case.get("stock_code", "")
    tracer = None
    if use_trace:
        tracer = Tracer(question=question, stock_code=code,
                        model=getattr(llm, "model_name", ""))
    result = run_agent_mode(
        question=question,
        stock_code=code,
        max_steps=max_steps,
        llm=llm,
        budget=from_settings(max_steps),
        tracer=tracer,
    )
    ok, failures = check_case(case, result)
    return {
        "id": case.get("id"),
        "question": question,
        "passed": ok,
        "failures": failures,
        "steps_used": result.get("steps_used", 0),
        "stopped": result.get("stopped"),
        "answer": result.get("answer", ""),
        "usage": result.get("usage") or {},
        "tools": [t.get("tool") for t in result.get("trajectory") or []],
        "trace_path": result.get("trace_path", ""),
    }


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # Windows GBK 控制台防 emoji 崩
        except Exception:  # noqa: BLE001
            pass

    args = parse_args(argv)
    cases = select_cases(load_suite(args.suite), args.case, args.limit)
    if not cases:
        print(f"⚠️ 没有匹配的用例：{args.suite}")
        return 1

    from utils.llm_factory import create_chat_model

    llm = create_chat_model(**({"model": args.model} if args.model else {}))
    model_name = getattr(llm, "model_name", None) or args.model or "未知模型"
    print(f"\n🧪 评测集 {Path(args.suite).name}：{len(cases)} 条（模型 {model_name}）\n")

    results = []
    for case in cases:
        try:
            item = run_one(case, llm, args.max_steps, not args.no_trace)
        except Exception as exc:  # noqa: BLE001 —— 一条炸了不该拖垮整批
            item = {
                "id": case.get("id"), "question": case.get("question", ""),
                "passed": False,
                "failures": [f"运行异常：{type(exc).__name__}: {exc}"],
                "steps_used": 0, "usage": {}, "tools": [], "trace_path": "",
            }
        results.append(item)
        elapsed = float((item.get("usage") or {}).get("elapsed_s") or 0)
        icon = "✅" if item["passed"] else "❌"
        print(f"{icon} [{item['id']}] {item['steps_used']} 步 / {elapsed:.1f}s  "
              f"{item['question']}")
        for reason in item["failures"]:
            print(f"     - {reason}")
        if item.get("trace_path"):
            print(f"     轨迹：{item['trace_path']}")

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    steps = sum(int(r.get("steps_used") or 0) for r in results)
    secs = sum(float((r.get("usage") or {}).get("elapsed_s") or 0) for r in results)
    tokens = sum(int((r.get("usage") or {}).get("total_tokens") or 0) for r in results)

    print("\n" + "=" * 60)
    print(f"通过 {passed}/{total} · 平均 {steps / total:.1f} 步 · "
          f"平均 {secs / total:.1f}s · 总 token {tokens}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"{stamp}.json"
    report_path.write_text(json.dumps({
        "suite": str(args.suite),
        "model": model_name,
        "passed": passed,
        "total": total,
        "avg_steps": round(steps / total, 2),
        "avg_seconds": round(secs / total, 2),
        "total_tokens": tokens,
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告：{report_path}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
