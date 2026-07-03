"""
LangChain Tool 定义 - 新闻搜索工具
"""
from langchain_core.tools import tool
from loguru import logger


def create_news_tools(akhare_client):
    """创建新闻搜索相关的 LangChain Tools"""

    @tool
    def get_stock_news(symbol: str, limit: int = 15) -> str:
        """获取股票相关的最新新闻和公告。

        Args:
            symbol: 股票代码
            limit: 获取新闻条数（默认15条）

        Returns:
            新闻列表文本
        """
        try:
            news = akhare_client.get_stock_news(symbol, limit=limit)
            if news:
                result = [f"共获取到 {len(news)} 条相关新闻：\n"]
                for i, n in enumerate(news[:limit]):
                    result.append(
                        f"{i+1}. [{n.get('datetime', '')}] {n.get('title', '')} "
                        f"(来源: {n.get('source', '未知')})"
                    )
                return "\n".join(result)
            return f"未获取到 {symbol} 的相关新闻"
        except Exception as e:
            return f"获取新闻失败: {str(e)}"

    @tool
    def get_market_news() -> str:
        """获取今日市场要闻和宏观动态。"""
        try:
            import akshare as ak

            df = ak.stock_info_global_em()
            if df is not None and not df.empty:
                titles = df.get("title", df.iloc[:, 0]).head(10).tolist() if "title" in df.columns else []
                if titles:
                    return "今日市场要闻:\n" + "\n".join([f"- {t}" for t in titles])
            return "暂无市场要闻"
        except Exception as e:
            return f"获取市场要闻失败: {str(e)}"

    return [get_stock_news, get_market_news]
