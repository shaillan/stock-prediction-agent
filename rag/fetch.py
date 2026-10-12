# -*- coding: utf-8 -*-
"""
第1步 取数据：巨潮资讯公告 → PDF → 纯文本

用 akshare 那个 stock_zh_a_disclosure_report_cninfo 接口会坏（列名对不上），
这里直接打巨潮资讯的 HTTP 接口，稳定可控。
"""
import io
import json
import os
import time
from typing import Dict, List, Optional

import requests
import fitz  # pymupdf

# ========== 巨潮资讯接口常量 ==========
_STOCK_LIST_URL = "http://www.cninfo.com.cn/new/data/szse_stock.json"  # 全部A股 code→orgId 映射
_QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"      # 公告列表
_PDF_BASE = "http://static.cninfo.com.cn/"                             # PDF 下载前缀

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
    "X-Requested-With": "XMLHttpRequest",
}


def _fmt_date(value) -> str:
    """巨潮的 announcementTime 是毫秒时间戳，转成 YYYY-MM-DD"""
    if isinstance(value, (int, float)) and value > 1e12:
        from datetime import datetime
        return datetime.fromtimestamp(value / 1000).strftime("%Y-%m-%d")
    return str(value or "")


def resolve_org_id(code: str) -> Optional[str]:
    """股票代码 → 巨潮的机构ID。茅台 600519 → gssh0600519"""
    r = requests.get(_STOCK_LIST_URL, headers=_HEADERS, timeout=20)
    for item in r.json().get("stockList", []):
        if item.get("code") == code:
            return item.get("orgId")
    return None


def fetch_announcements(
    code: str,
    start_date: str = "2026-01-01",
    end_date: str = "2026-10-11",
    limit: int = 30,
    cache_file: Optional[str] = None,
) -> List[Dict]:
    """
    拉取某只股票一段时间的公告，下载 PDF 并抽成纯文本。

    返回 [{"title", "date", "text", "url"}, ...]（text 为空的跳过）。
    结果会缓存到 cache_file（JSON），避免重复下载。
    """
    if cache_file and os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)

    org_id = resolve_org_id(code)
    if not org_id:
        raise ValueError(f"找不到股票 {code} 的机构ID")

    payload = {
        "pageNum": 1, "pageSize": limit, "column": "szse", "tabName": "fulltext",
        "plate": "", "stock": f"{code},{org_id}", "searchkey": "", "secid": "",
        "category": "", "trade": "", "seDate": f"{start_date}~{end_date}",
        "sortName": "", "sortType": "", "isHLtitle": "true",
    }
    r = requests.post(_QUERY_URL, data=payload, headers=_HEADERS, timeout=20)
    anns = r.json().get("announcements") or []

    results: List[Dict] = []
    for a in anns:
        title = (a.get("announcementTitle") or "").strip()
        rel = a.get("adjunctUrl") or ""
        if not rel:
            continue
        pdf_url = _PDF_BASE + rel
        try:
            text = _download_and_extract(pdf_url)
            if text.strip():
                results.append({
                    "title": title,
                    "date": _fmt_date(a.get("announcementTime")),
                    "text": text,
                    "url": pdf_url,
                })
        except Exception as e:
            print(f"  ⚠️ 跳过 {title[:30]}：{type(e).__name__}")
        time.sleep(0.3)  # 礼貌限速，别把巨潮打挂

    if cache_file:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False)
    return results


def _download_and_extract(pdf_url: str) -> str:
    """下载 PDF 并用 pymupdf 抽全部文字"""
    r = requests.get(pdf_url, headers=_HEADERS, timeout=30)
    doc = fitz.open(stream=r.content, filetype="pdf")
    try:
        return "".join(page.get_text() for page in doc)
    finally:
        doc.close()
