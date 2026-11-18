# -*- coding: utf-8 -*-
"""轨迹落盘：每次运行一份 JSONL，脱敏后写入 runs/

为什么逐事件写而不是结束时一次性写：进程崩了 / 用户 Ctrl-C，前面发生过什么
仍然留在磁盘上；复盘「它为什么改道」靠的正是这些中间步骤。

脱敏是硬约束，不是可选项——项目约束里「不要把密钥上传了」在架构层的落点，
就是所有落盘内容先过 mask：sk- 开头的 key、api_key=/authorization: 这类键值。
"""
import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from harness.types import RunRecord

_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|authorization|secret[_-]?key)\b"
        r"\s*[:=]\s*[\"']?[^\s\"',}]+"
    ),
]


def mask_text(text: str) -> str:
    """把疑似密钥替换成 ***；只处理字符串，非字符串原样返回"""
    if not isinstance(text, str):
        return text
    for pat in _PATTERNS:
        text = pat.sub(lambda m: (m.group(1) + "=***") if m.lastindex else "sk-***", text)
    return text


def mask_obj(obj: Any, _depth: int = 0) -> Any:
    """递归脱敏 dict/list/str；深度封顶，防止异常对象把递归拖死"""
    if _depth > 8:
        return "<max-depth>"
    if isinstance(obj, str):
        return mask_text(obj)
    if isinstance(obj, dict):
        return {str(k): mask_obj(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [mask_obj(v, _depth + 1) for v in obj]
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    return mask_text(str(obj))


class Tracer:
    """一次运行的轨迹记录器。

    用法：
        tracer = Tracer(question=..., stock_code=..., model=...)
        for ev in iter_agent_events(..., tracer=tracer): ...
        tracer.path        # 落盘位置

    runtime 会在 done 事件处自动 close()，调用方不用手动收尾。
    """

    def __init__(self, question: str = "", stock_code: str = "", model: str = "",
                 root: Optional[str] = None, run_id: Optional[str] = None,
                 enabled: Optional[bool] = None):
        from config import settings

        # enabled 不传时读 config 开关：UI 和 CLI 就不用手写一份判断
        self.enabled = settings.harness_trace_enabled if enabled is None else enabled
        self.question = mask_text(question or "")
        self.stock_code = stock_code or ""
        self.model = model or ""
        self.run_id = run_id or f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
        self.root = Path(root or settings.harness_trace_dir)
        self._started = time.monotonic()
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.path: Optional[Path] = None
        self.index_path = self.root / "index.jsonl"
        self.record: Optional[RunRecord] = None
        self._closed = False
        if not self.enabled:
            return

        day = self.root / f"{datetime.now():%Y%m%d}"
        day.mkdir(parents=True, exist_ok=True)
        self.path = day / f"{self.run_id}.jsonl"

    # ---------- 写盘 ----------
    def _append(self, payload: dict) -> None:
        if not self.enabled or self.path is None:
            return
        line = json.dumps(payload, ensure_ascii=False, default=str)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def emit(self, event: dict) -> None:
        """逐事件落盘；done 事件顺带收尾并写索引"""
        if not self.enabled:
            return
        safe = mask_obj(event)
        self._append({"ts": datetime.now().isoformat(timespec="milliseconds"),
                      "run_id": self.run_id, "event": safe})
        if event.get("type") == "done":
            self.close(event)

    def close(self, done: dict) -> None:
        """把 done 事件压成一行索引，方便 `tail runs/index.jsonl` 看全部运行"""
        if self._closed or not self.enabled:
            return
        self._closed = True
        traj = done.get("trajectory") or []
        self.record = RunRecord(
            run_id=self.run_id,
            question=self.question,
            stock_code=self.stock_code,
            model=self.model,
            steps_used=int(done.get("steps_used") or 0),
            stopped=done.get("stopped") or "answered",
            tools=[t.get("tool", "") for t in traj],
            usage=done.get("usage") or {},
            wall_s=time.monotonic() - self._started,
            trace_path=self.rel_path(),
        )
        try:
            with self.index_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(self.record.to_dict(), ensure_ascii=False) + "\n")
        except OSError:  # 索引写失败不该让主流程陪葬
            pass

    def rel_path(self) -> str:
        if self.path is None:
            return ""
        try:
            return str(self.path.relative_to(Path.cwd()))
        except ValueError:
            return str(self.path)

    def usage_summary(self) -> dict:
        return self.record.usage if self.record else {}
