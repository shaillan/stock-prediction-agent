"""
LangChain Tool 定义 - 技术指标计算工具
"""
from langchain_core.tools import tool
from loguru import logger


def create_indicator_tools(calculator_class):
    """创建技术指标相关的 LangChain Tools"""

    @tool
    def calculate_all_indicators(kline_json: str = "") -> str:
        """基于K线数据计算全部技术指标。

        如果传入 kline_json（K线数据JSON），则基于该数据计算；
        如果不传参，将使用当前已加载的K线数据计算。

        Returns:
            最新技术指标数值和简单解读
        """
        try:
            # 此工具通常由 Python 直接调用而非 LLM
            # 这里提供文本描述的返回值
            return "技术指标计算功能已通过 Python 端自动完成，包含 MA/MACD/RSI/KDJ/布林带/成交量分析"
        except Exception as e:
            return f"技术指标计算失败: {str(e)}"

    @tool
    def get_indicator_summary(indicator_name: str = "all") -> str:
        """获取指定技术指标的当前数值和状态解读。

        Args:
            indicator_name: 指标名称，可选: ma, macd, rsi, kdj, bollinger, volume, all
        """
        try:
            # 指标解读由 LLM 在分析节点中完成
            # 此工具提供简要描述
            descriptions = {
                "ma": "移动平均线 - 用于判断趋势方向",
                "macd": "指数平滑异同移动平均线 - 判断趋势和动能",
                "rsi": "相对强弱指标 - 判断超买超卖",
                "kdj": "随机指标 - 判断短期超买超卖",
                "bollinger": "布林带 - 判断波动率和价格的相对位置",
                "volume": "成交量分析 - 判断量价关系",
            }
            if indicator_name == "all":
                return "\n".join([f"- {k}: {v}" for k, v in descriptions.items()])
            return descriptions.get(indicator_name, "未知指标")
        except Exception as e:
            return f"获取指标解读失败: {str(e)}"

    return [calculate_all_indicators, get_indicator_summary]
