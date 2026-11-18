# -*- coding: utf-8 -*-
"""工具注册表：schema + 超时 + 重试 + 缓存 + 统一错误口径

相对 agent_mode/tools.py 原来的「两个 dict」多了三件事：
- 超时：AKShare 卡住时线程 join 超时返回文本，不会拖死整轮
- 重试：网络抖动自动再来一次；超时不重试（重试只会等更久）
- 缓存：同一轮里模型重复问同一件事，第二次直接命中

错误口径与旧版 `_dispatch` 完全一致（未知工具 / 工具执行失败 / 返回空 / 超时），
测试 cache/agent_mode_check.py 的 T3 断言的正是这些字符串。
"""
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from harness.types import ToolSpec

_REGISTRY: Dict[str, ToolSpec] = {}
_CACHE: Dict[str, Tuple[float, str]] = {}
_LOCK = threading.Lock()
DEFAULT_TIMEOUT_S = 20.0


def register(name: str, description: str, impl, schema: Optional[dict] = None,
             timeout_s: float = DEFAULT_TIMEOUT_S, retries: int = 0,
             cache_ttl_s: float = 0.0, tags: Optional[List[str]] = None) -> ToolSpec:
    """注册一个工具；重复注册以最后一次为准（便于测试替换）"""
    spec = ToolSpec(
        name=name, description=description, impl=impl, schema=schema or {},
        timeout_s=timeout_s, retries=max(0, retries),
        cache_ttl_s=max(0.0, cache_ttl_s), tags=list(tags or []),
    )
    with _LOCK:
        _REGISTRY[name] = spec
    return spec


def get(name: str) -> Optional[ToolSpec]:
    return _REGISTRY.get(name)


def names() -> List[str]:
    return sorted(_REGISTRY)


def impl_map() -> Dict[str, Any]:
    return {name: spec.impl for name, spec in _REGISTRY.items()}


def clear() -> None:
    with _LOCK:
        _REGISTRY.clear()
        _CACHE.clear()


def _cache_key(name: str, args: dict) -> str:
    try:
        import json
        return name + "|" + json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return name + "|" + str(sorted(args.items()))


def _call_with_timeout(fn, timeout_s: float):
    """在守护线程里跑 fn，join 超时就抛 TimeoutError。

    用裸 threading 而不是 ThreadPoolExecutor：后者退出时要 join 工作线程，
    一个卡死的 AKShare 请求会让整个进程退不掉；daemon 线程则允许被丢弃。
    """
    box: Dict[str, Any] = {}

    def _target():
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 —— 原样回传给调用方
            box["error"] = exc

    worker = threading.Thread(target=_target, daemon=True, name="harness-tool")
    worker.start()
    worker.join(timeout_s)
    if worker.is_alive():
        raise TimeoutError(f"{timeout_s:.0f}s")
    if "error" in box:
        raise box["error"]
    return box.get("value")


def execute(name: str, args: Optional[dict], impls_override: Optional[Dict[str, Any]] = None
            ) -> Tuple[str, Dict[str, Any]]:
    """执行工具，返回 (给模型读的文本, 运行元数据)。

    永远不抛异常：失败也返回一段说明文本，由模型决定改道还是放弃——
    延续「报错当内容回喂」的哲学。元数据（耗时/缓存/重试）只给轨迹用。
    """
    args = args if isinstance(args, dict) else {}
    started = time.monotonic()
    meta: Dict[str, Any] = {"elapsed_ms": 0, "cached": False,
                            "retries": 0, "timed_out": False}
    if impls_override is not None:
        # 调用方自带实现（测试 / 定制场景）：只用注册表的超时，重试与缓存归调用方
        impl = impls_override.get(name)
        known = sorted(impls_override)
        spec = _REGISTRY.get(name)
        use_cache = False
        retries = 0
    else:
        spec = _REGISTRY.get(name)
        impl = spec.impl if spec else None
        known = names()
        use_cache = bool(spec and spec.cache_ttl_s > 0)
    timeout_s = spec.timeout_s if spec else DEFAULT_TIMEOUT_S
    if impls_override is None:
        retries = spec.retries if spec else 0

    if impl is None:
        meta["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        return f"未知工具 {name}。可用工具: {'、'.join(known)}", meta

    key = _cache_key(name, args)
    if use_cache:
        with _LOCK:
            hit = _CACHE.get(key)
        if hit and hit[0] > time.time():
            meta.update(cached=True, elapsed_ms=int((time.monotonic() - started) * 1000))
            return hit[1], meta

    last_exc: Optional[BaseException] = None
    for attempt in range(retries + 1):
        try:
            value = _call_with_timeout(lambda: impl(**args), timeout_s)
            text = value if isinstance(value, str) else str(value)
            text = text or "（工具返回空）"
            if use_cache:
                with _LOCK:
                    _CACHE[key] = (time.time() + spec.cache_ttl_s, text)
            meta.update(retries=attempt, elapsed_ms=int((time.monotonic() - started) * 1000))
            return text, meta
        except TimeoutError:
            meta.update(timed_out=True, elapsed_ms=int((time.monotonic() - started) * 1000))
            return (f"工具执行超时（{timeout_s:.0f}s）：{name} 没有在限定时间内返回，"
                    f"先改用其它信息，别重复调用它。"), meta
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            meta["retries"] = attempt + 1
            if attempt < retries:
                logger.warning(f"[harness] {name} 第 {attempt + 1} 次失败，重试：{exc}")
                time.sleep(0.3 * (attempt + 1))

    meta["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    return (f"工具执行失败: {type(last_exc).__name__}: {last_exc}"
            f"（最多重试一次，然后改用其它信息）"), meta
