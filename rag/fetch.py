# -*- coding: utf-8 -*-
"""
第1步 取数据：巨潮资讯公告 → PDF → 纯文本

用 akshare 那个 stock_zh_a_disclosure_report_cninfo 接口会坏（列名对不上），
这里直接打巨潮资讯的 HTTP 接口，稳定可控。
"""
import io
import json
import os
import re
import time
from datetime import date, timedelta
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


# 定期报告 = 半年报/年报/季报/审计报告。这类动辄几百页，
# 里面的股东持股表、财务报表被切成大量"增持/减持/股东"数字碎片，
# 字面命中关键词但语义是垃圾，会把真正一句话说清的临时公告挤出排行榜。
# 注意用「精确子串」而不是「年度」这种宽泛词，否则会误伤
# 《关于调整2025年年度利润分配方案…》《2025年年度权益分派实施公告》这类真信号。
REGULAR_REPORT_PATTERNS = ["半年度报告", "年度报告", "季度报告", "审计报告"]


def is_regular_report(title: str) -> bool:
    """标题是否属于定期报告（半年报/年报/季报/审计报告）"""
    t = title or ""
    return any(p in t for p in REGULAR_REPORT_PATTERNS)


# 独董文书 = 证监会统一模板，通篇是"本人不存在……""提名人认为……"的固定条文，
# 没有一条本公司特有的信息。但它们含"股东""控股股东"这类通用词，字面命中、
# 语义为零，专门抢检索名额（实测 4 篇声明里 控股股东×19、股东×53，而 增持/减持 各 0 次）。
#
# 为什么用这么长的子串而不是"独立董事"：那样会误伤《关于独立董事辞职的公告》——
# 独董辞职是实打实的信号（可能牵出内控/治理问题），不能当噪音删掉。
#
# 注意：实测**不能**顺手把《…法律意见书》一起过滤。它在向量那一路排名很高，
# 是 RRF 融合里的"配重块"；删掉它反而会让《股东会通知》浮上来顶掉正确答案第 1 名。
# 详见 rag/TUTORIAL.md 第十一节。
DIRECTOR_BOILERPLATE_PATTERNS = [
    "独立董事候选人声明",   # 候选人本人签的声明与承诺
    "独立董事提名人声明",   # 提名方（控股股东）签的声明与承诺，噪音最重
    "独立董事述职报告",     # 年度例行述职，通篇套话
]


def is_director_boilerplate(title: str) -> bool:
    """标题是否是独董模板文书（候选人/提名人声明、述职报告）"""
    t = title or ""
    return any(p in t for p in DIRECTOR_BOILERPLATE_PATTERNS)


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


def _strip_tags(text: str) -> str:
    """巨潮在 isHLtitle=true 时会给标题加 <em> 高亮标签，去掉"""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def fetch_announcement_list(
    code: str,
    days: int = 90,
    limit: int = 40,
    exclude_regular_reports: bool = False,
) -> List[Dict]:
    """只拉公告的标题 + 日期 + 链接，**不下载 PDF**。

    简报、异动监控这类场景只需要「公司发了什么公告」，不需要全文；
    下载并解析 30 份 PDF 要 30 秒以上，而这里一次 HTTP 请求就够。

    和 RAG 建库的口径**故意不同**：那边必须过滤定期报告，因为几百页的
    股东持股表会切成大量数字碎片、把真信号挤出排行榜；而这里只有标题，
    「发布了半年报」本身正是用户想知道的重大事件，所以默认**保留**。
    只过滤独董候选人/提名人声明这类纯模板文书。
    """
    org_id = resolve_org_id(code)
    if not org_id:
        raise ValueError(f"找不到股票 {code} 的机构ID")

    end = date.today()
    start = end - timedelta(days=days)
    payload = {
        "pageNum": 1, "pageSize": min(limit * 3, 100),
        "column": "szse", "tabName": "fulltext",
        "plate": "", "stock": f"{code},{org_id}", "searchkey": "", "secid": "",
        "category": "", "trade": "",
        "seDate": f"{start:%Y-%m-%d}~{end:%Y-%m-%d}",
        "sortName": "", "sortType": "", "isHLtitle": "true",
    }
    r = requests.post(_QUERY_URL, data=payload, headers=_HEADERS, timeout=20)
    r.raise_for_status()
    anns = r.json().get("announcements") or []

    results: List[Dict] = []
    for a in anns:
        title = _strip_tags(a.get("announcementTitle") or "")
        if not title:
            continue
        if is_director_boilerplate(title):
            continue
        if exclude_regular_reports and is_regular_report(title):
            continue
        rel = a.get("adjunctUrl") or ""
        results.append({
            "title": title,
            "date": _fmt_date(a.get("announcementTime")),
            "url": _PDF_BASE + rel if rel else "",
        })
        if len(results) >= limit:
            break
    return _drop_digest_duplicates(results)


def _drop_digest_duplicates(items: List[Dict]) -> List[Dict]:
    """同一份文件常有「正本 + 摘要/英文版」，简报里只留正本"""
    titles = {i.get("title", "") for i in items}
    out: List[Dict] = []
    for item in items:
        t = item.get("title", "")
        if any(t.endswith(s) and t[:-len(s)] in titles for s in ("摘要", "英文版")):
            continue
        out.append(item)
    return out


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
