"""
分析详情展开面板组件 - 展示技术分析、新闻情绪、公告检索、基本面等详细内容
"""
import streamlit as st
from typing import Dict, Optional


def render_analysis_details(
    technical_result: Optional[str] = None,
    sentiment_result: Optional[str] = None,
    financial_data: Optional[Dict] = None,
    final_report: Optional[str] = None,
    realtime_quote: Optional[Dict] = None,
    announcement_context: Optional[str] = None,
    rag_enabled: bool = True,
    rag_error: Optional[str] = None,
) -> None:
    """渲染分析详情展开面板

    Args:
        technical_result: 技术分析文本 (Markdown)
        sentiment_result: 新闻情绪分析文本 (Markdown)
        financial_data: 财务指标 Dict
        final_report: 最终完整报告 (Markdown)
        realtime_quote: 实时行情 Dict
        announcement_context: RAG 检索到的"公告动态"原文，空串/None = 没命中
        rag_enabled: 侧边栏的公告检索开关，用来区分"没开"和"没命中"
        rag_error: 公告检索的报错（若有），用来暴露流水线的静默降级
    """
    st.markdown("## 📋 详细分析")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 技术分析",
        "📰 新闻情绪",
        "📢 公告",
        "💰 基本面",
        "📝 完整报告",
        "🏆 战绩",
        "📖 新手科普",
    ])

    # ===== Tab 1: 技术分析 =====
    with tab1:
        if technical_result:
            st.markdown(technical_result)
        else:
            st.info("暂无技术分析数据")

    # ===== Tab 2: 新闻情绪 =====
    with tab2:
        if sentiment_result:
            st.markdown(sentiment_result)
        else:
            st.info("暂无新闻情绪分析数据")

    # ===== Tab 3: 公告检索（RAG）=====
    with tab3:
        _render_announcements(announcement_context, rag_enabled, rag_error)

    # ===== Tab 4: 基本面 =====
    with tab4:
        if financial_data:
            # 表格展示
            col1, col2 = st.columns(2)

            metrics = [
                ("市盈率 (PE)", financial_data.get("pe")),
                ("市净率 (PB)", financial_data.get("pb")),
                ("市销率 (PS)", financial_data.get("ps")),
                ("ROE", financial_data.get("roe")),
                ("ROA", financial_data.get("roa")),
                ("毛利率", financial_data.get("gross_margin")),
                ("净利率", financial_data.get("net_margin")),
                ("营收增长率", financial_data.get("revenue_growth")),
                ("利润增长率", financial_data.get("profit_growth")),
                ("资产负债率", financial_data.get("debt_ratio")),
                ("总市值(亿)", financial_data.get("total_market_value")),
                ("流通市值(亿)", financial_data.get("circulating_market_value")),
            ]

            for i, (label, value) in enumerate(metrics):
                col = col1 if i % 2 == 0 else col2
                with col:
                    if value is not None:
                        formatted = f"{float(value):.2f}" if isinstance(value, (int, float)) else str(value)
                        st.metric(label, formatted)
                    else:
                        st.metric(label, "N/A")
        else:
            st.info("暂无基本面数据")

        # 实时行情
        if realtime_quote:
            st.markdown("---")
            st.markdown("### 📡 实时行情")
            q = realtime_quote
            cols = st.columns(4)
            cols[0].metric("最新价", f"¥{q.get('price', 'N/A')}")
            change_pct = q.get('change_pct', 0)
            # delta_color="inverse" 让涨显示红色、跌显示绿色（中式约定，Streamlit 默认是反的）
            cols[1].metric("涨跌幅", f"{change_pct:+.2f}%",
                          delta=f"{change_pct:+.2f}%" if change_pct else None,
                          delta_color="inverse")
            cols[2].metric("成交量", f"{q.get('volume', 0):,.0f}")
            turnover = q.get("turnover")
            cols[3].metric(
                "换手率",
                f"{turnover:.2f}%" if isinstance(turnover, (int, float)) else "N/A",
            )

    # ===== Tab 5: 完整报告 =====
    with tab5:
        if final_report:
            st.markdown(final_report)
        else:
            st.info("暂无完整报告")

    # ===== Tab 6: 战绩 =====
    with tab6:
        _render_track_record()

    # ===== Tab 7: 新手科普 =====
    with tab7:
        from ui.components.beginner_guide import render_beginner_guide
        render_beginner_guide(financial_data=financial_data)

    # 免责声明
    st.markdown("""
    <div class="disclaimer">
        <strong>⚠️ 免责声明</strong><br>
        本报告由 LLM 工作流自动生成，所有分析和预测均基于历史数据和公开信息的统计分析，<strong>仅供参考，不构成任何投资建议</strong>。
        股市有风险，投资需谨慎。投资者应当独立做出投资决策，并自行承担投资风险。
        AI 预测具有不确定性，过往表现不代表未来收益。
    </div>
    """, unsafe_allow_html=True)


def _render_announcements(
    announcement_context: Optional[str],
    rag_enabled: bool,
    rag_error: Optional[str],
) -> None:
    """渲染"公告"tab。

    显示的就是 rag.service.build_stock_context 的返回值**原文**——和塞进预测
    prompt 的那段字符完全一致（agent/prompts/system_prompts.py），便于核对
    检索是否真的生效。

    三种"空"要分开提示：检索关闭 / 检索报错 / 确实没命中。
    流水线对公告检索是静默降级的（失败不中断分析，只是少一路信号），
    不在这里区分的话，RAG 挂掉时界面上一点痕迹都没有。
    """
    if announcement_context:
        n = sum(1 for ln in announcement_context.splitlines() if ln.startswith("- **《"))
        st.caption(f"命中 {n} 条公告片段 · 以下即流水线实际喂给预测模型的原文")
        st.markdown(announcement_context)
        st.markdown("---")
        st.caption(
            '想看每条命中的距离 / 关键词得分 / gap：'
            '`python -m rag.cli diagnose "问题" --code 600519`（详见 rag/TUTORIAL.md）'
        )
        return

    if not rag_enabled:
        st.info("公告全文检索（RAG）已在左侧边栏关闭，本次分析未使用公告信号。")
        return

    if rag_error:
        st.error("公告检索失败，本次预测未包含公告信号。")
        st.caption(f"错误详情：{rag_error}")
        st.caption("流水线对公告检索是静默降级的——失败不会中断分析，只是少一路信号。")
        return

    st.info(
        "本次没有命中公告片段。可能是这只股票在该时间窗内没有公告，"
        "也可能是公告没命中固定的 6 个研究问题（减持/回购/业绩预告/合同/分红/风险）。"
    )


def _render_track_record() -> None:
    """「🏆 战绩」tab：历史预测 vs 实际走势的自动复盘

    数据来自 records/predictions.jsonl（run_agent 末尾自动存档）。
    """
    from utils.track_record import load_records, review_pending, summarize

    if st.button("🔄 复盘到期预测（拉最新行情判定对错）"):
        with st.spinner("正在复盘…"):
            stats = review_pending()
        st.toast(f"复盘完成：判定 {stats['reviewed']} 条，未到期/缺数据跳过 {stats['skipped']} 条"
                 f"{'，失败 ' + str(stats['failed']) + ' 条' if stats['failed'] else ''}")

    records = load_records()
    if not records:
        st.info(
            "还没有存档的预测。每次分析完成后会自动存档；等预测期（1-5 个交易日）"
            "走完后回到这里点「复盘」，就能看到当初的预测对不对。"
        )
        return

    # 按股票筛选
    stocks = sorted({r.get("stock_code", "") for r in records if r.get("stock_code")})
    pick = st.selectbox("筛选", ["全部"] + stocks)
    scope = records if pick == "全部" else [r for r in records if r.get("stock_code") == pick]

    s = summarize(scope)
    cols = st.columns(4)
    cols[0].metric("存档预测", s["total"])
    cols[1].metric("已复盘", s["reviewed"])
    cols[2].metric(
        "方向命中率",
        f"{s['hit_rate'] * 100:.0f}%" if s["hit_rate"] is not None else "—",
    )
    cols[3].metric(
        "平均置信度",
        f"{s['avg_confidence'] * 100:.0f}%" if s["avg_confidence"] is not None else "—",
    )

    st.markdown("##### 明细")
    rows = []
    for r in sorted(scope, key=lambda x: x.get("prediction_date", ""), reverse=True)[:30]:
        o = r.get("outcome") or {}
        if "direction_hit" in o:
            verdict = "✓ 命中" if o["direction_hit"] else "✗ 未命中"
        elif o.get("error"):
            verdict = "⚠️ " + o["error"]
        else:
            verdict = "⏳ 未到期"
        rows.append({
            "日期": r.get("prediction_date"),
            "股票": r.get("stock_name") or r.get("stock_code"),
            "预测": r.get("trend"),
            "置信度": f"{r.get('confidence', 0) * 100:.0f}%",
            "期内涨跌": f"{o['change_pct']:+.2f}%" if "change_pct" in o else "",
            "判定": verdict,
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("##### 置信度校准")
    st.dataframe(s["calibration"], use_container_width=True, hide_index=True)
    st.caption(
        "校准的含义：置信度 0.6~0.8 的预测，实际命中率应落在 60%~80%。"
        "两列差得越远，说明模型的自信越不可信。"
    )
    st.caption(
        "判定规则：看涨=期末涨超 +0.5%；看跌=跌超 -0.5%；震荡=期内涨跌幅在 ±3% 内。"
        "涨跌幅 = 预测日之后第 N 个交易日的收盘价 vs 预测日收盘/预测时价格。"
        "判定由代码完成，不经 LLM。"
    )
