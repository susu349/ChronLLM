"""
主Agent (Main Agent)
负责处理用户问题并进行编排并调用工具
"""
from datetime import datetime
from typing import Dict, Any, List
from .base_agent import BaseAgent


class MainAgent(BaseAgent):
    """主Agent - 处理用户问题并编排工具调用"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(
            name="main",
            description="处理用户问题并进行编排并调用工具",
            config=config
        )
        self.tools = []

    def _execute_impl(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        user_input = input_data.get("input", "")
        context = input_data.get("context", {})

        # 分析用户意图
        intent = self._analyze_intent(user_input)

        # 规划工具调用
        tool_calls = self._plan_tool_calls(intent, user_input, context)

        # 生成回复
        reply = self._generate_reply(intent, user_input, context, tool_calls)

        return {
            "status": "success",
            "intent": intent,
            "reply": reply,
            "tool_calls": tool_calls,
            "data": {
                "intent": intent,
                "reply": reply,
            },
            "timestamp": datetime.now().isoformat()
        }

    def _analyze_intent(self, user_input: str) -> str:
        """分析用户意图"""
        input_lower = user_input.lower()

        intent_keywords = {
            "plan": ["规划", "安排", "计划", "今天", "明天", "schedule", "plan"],
            "recipe": ["吃什么", "菜单", "食谱", "recipe", "food", "cook"],
            "weather": ["天气", "温度", "下雨", "weather", "temperature"],
            "task": ["任务", "todo", "task"],
        }

        for intent, keywords in intent_keywords.items():
            if any(kw in input_lower for kw in keywords):
                return intent

        return "chat"

    def _plan_tool_calls(self, intent: str, user_input: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """规划工具调用"""
        calls = []

        if intent == "plan":
            calls.append({"tool": "planning_agent"})
        elif intent == "recipe":
            calls.append({"tool": "chef_agent"})
        elif intent == "weather":
            calls.append({"tool": "weather_agent"})

        return calls

    def _generate_reply(self, intent: str, user_input: str, context: Dict[str, Any], tool_calls: List[Dict[str, Any]]) -> str:
        """生成回复"""
        if intent == "plan":
            return "好的，让我为您规划一下..."
        elif intent == "recipe":
            return "让我为您推荐一些美食..."
        elif intent == "weather":
            return "让我查一下天气..."
        else:
            return f"收到您的消息了：{user_input}"

    def get_capabilities(self) -> List[str]:
        return [
            "意图识别",
            "工具调用编排",
            "对话管理",
            "问题理解",
        ]
