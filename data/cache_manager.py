"""
二级缓存管理 - 内存 LRU + SQLite 磁盘缓存
"""
import json
import os
import sqlite3
import time
import threading
from typing import Any, Optional
from collections import OrderedDict
from loguru import logger


class MemoryCache:
    """线程安全的内存 LRU 缓存"""

    def __init__(self, max_size: int = 128):
        self.max_size = max_size
        self._cache: OrderedDict[str, tuple] = OrderedDict()  # key -> (value, expiry_time)
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            value, expiry = self._cache[key]
            if expiry > 0 and time.time() > expiry:
                del self._cache[key]
                return None
            # 移到末尾（最近使用）
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: int = 0):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            expiry = time.time() + ttl if ttl > 0 else 0
            self._cache[key] = (value, expiry)
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def invalidate(self, prefix: str = ""):
        with self._lock:
            if prefix:
                keys = [k for k in self._cache if k.startswith(prefix)]
                for k in keys:
                    del self._cache[k]
            else:
                self._cache.clear()

    def __len__(self):
        with self._lock:
            return len(self._cache)


class DiskCache:
    """SQLite 磁盘缓存"""

    def __init__(self, db_path: str = "cache/stock_cache.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._lock = threading.RLock()  # RLock: get() 内部调用 delete() 不会死锁
        self._init_db()

    def _init_db(self):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        ttl INTEGER NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON cache(created_at)")

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT value, created_at, ttl FROM cache WHERE key = ?", (key,)
                ).fetchone()
            if row is None:
                return None
            value_str, created_at, ttl = row
            if ttl > 0 and time.time() - created_at > ttl:
                self.delete(key)
                return None
            try:
                return json.loads(value_str)
            except json.JSONDecodeError:
                return None

    def set(self, key: str, value: Any, ttl: int = 0):
        with self._lock:
            value_str = json.dumps(value, ensure_ascii=False, default=str)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, created_at, ttl) VALUES (?, ?, ?, ?)",
                    (key, value_str, time.time(), ttl),
                )

    def delete(self, key: str):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))

    def clear_expired(self):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM cache WHERE ttl > 0 AND created_at + ttl < ?",
                    (time.time(),),
                )

    def invalidate(self, prefix: str = ""):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                if prefix:
                    conn.execute("DELETE FROM cache WHERE key LIKE ?", (f"{prefix}%",))
                else:
                    conn.execute("DELETE FROM cache")


class CacheManager:
    """二级缓存管理器"""

    def __init__(self, mem_size: int = 128, disk_path: str = "cache/stock_cache.db"):
        self.memory = MemoryCache(max_size=mem_size)
        self.disk = DiskCache(db_path=disk_path)

    def get(self, key: str) -> Optional[Any]:
        """先从内存查，再从磁盘查"""
        value = self.memory.get(key)
        if value is not None:
            logger.debug(f"缓存命中(内存): {key}")
            return value
        value = self.disk.get(key)
        if value is not None:
            logger.debug(f"缓存命中(磁盘): {key}")
            # 回填内存（不设 TTL，磁盘 TTL 已控制）
            self.memory.set(key, value, ttl=60)
            return value
        logger.debug(f"缓存未命中: {key}")
        return None

    def set(self, key: str, value: Any, ttl: int = 0):
        """同时写入内存和磁盘"""
        mem_ttl = min(ttl, 300) if ttl > 0 else 60  # 内存最多缓存5分钟
        self.memory.set(key, value, ttl=mem_ttl)
        self.disk.set(key, value, ttl=ttl)

    def invalidate(self, prefix: str = ""):
        self.memory.invalidate(prefix)
        self.disk.invalidate(prefix)

    def clear_expired(self):
        self.disk.clear_expired()
