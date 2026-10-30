# -*- coding: utf-8 -*-
"""
Agent 模式 —— 与主工作流（agent/）并列的第二种范式

- agent/      ：工作流。代码决定下一步做什么，固定几次 LLM 调用，路径可预测
- agent_mode/ ：Agent。LLM 看着工具结果自己决定下一步（ReAct 循环），
                适合「路径写不出来」的开放式问题（README 里的例子：
                查公告→发现回购→再去查资金流→对不上→回头核对口径）

两个模式共用同一套数据层（data/、rag/）与战绩机制（utils/track_record）。
"""
