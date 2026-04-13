"""
系统编排器 (System Orchestrator)
整合所有Agent，提供统一的入口
"""
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from .base_agent import BaseAgent, AgentStatus, AgentEvaluation
from .supervisor import SupervisorAgent
from .ceo_agent import CEOAgent
from .main_agent import MainAgent
from .agent_config import (
    SystemConfig,
    get_agent_config,
    save_agent_config,
    get_agent_config_schema,
)


class SystemOrchestrator:
    """系统编排器 - 统一入口"""

    def __init__(self):
        self.config = get_agent_config()
        self.supervisor = SupervisorAgent(self.config.supervisor_config)
        self.ceo = CEOAgent(self.config.ceo_config)

        # 初始化所有Agent
        self._init_agents()

        # 注册到Supervisor
        self._register_agents_to_supervisor()

        # 设置依赖关系
        self._setup_dependencies()

    def _init_agents(self):
        """初始化所有Agent"""
        self.agents = {
            "main": MainAgent(self.config.agents.get("main", {}).__dict__ if "main" in self.config.agents else {}),
            # 其他Agent将在使用时动态初始化
        }

    def _register_agents_to_supervisor(self):
        """注册Agent到Supervisor"""
        for name, agent in self.agents.items():
            self.supervisor.register_agent(agent)

    def _setup_dependencies(self):
        """设置Agent依赖关系"""
        self.supervisor.set_dependencies("planning", ["context_compression"])
        self.supervisor.set_dependencies("audit", ["planning"])
        self.supervisor.set_dependencies("task_decomposition", ["main"])
        self.supervisor.set_dependencies("event_handler", ["task_decomposition"])

    def process_request(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """处理用户请求（主入口）"""
        if context is None:
            context = {}

        # 1. 分析请求类型
        task_type = self._classify_request(user_input)

        # 2. 交给Supervisor处理
        result = self.supervisor.execute({
            "task_type": task_type,
            "input": user_input,
            "context": context,
        })

        return result

    def _classify_request(self, user_input: str) -> str:
        """分类请求类型"""
        input_lower = user_input.lower()

        if any(kw in input_lower for kw in ["规划", "安排", "plan", "schedule"]):
            return "daily_plan"
        elif any(kw in input_lower for kw in ["吃", "菜单", "食谱", "recipe", "food"]):
            return "recipe"
        elif any(kw in input_lower for kw in ["天气", "weather"]):
            return "weather"
        elif any(kw in input_lower for kw in ["任务", "task", "todo"]):
            return "task_decomposition"
        else:
            return "chat"

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "timestamp": datetime.now().isoformat(),
            "config": self.config.to_dict(),
            "supervisor": self.supervisor.get_status_report(),
            "ceo": {
                "last_optimization": self.ceo.last_optimization_date.isoformat() if self.ceo.last_optimization_date else None,
                "should_optimize": self.ceo.should_optimize(),
            },
        }

    def get_config_ui_schema(self) -> Dict[str, Any]:
        """获取配置UI Schema"""
        return get_agent_config_schema()

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """更新配置"""
        try:
            # 更新系统配置
            if "global_settings" in new_config:
                self.config.global_settings.update(new_config["global_settings"])
            if "supervisor_config" in new_config:
                self.config.supervisor_config.update(new_config["supervisor_config"])
            if "ceo_config" in new_config:
                self.config.ceo_config.update(new_config["ceo_config"])

            # 更新Agent配置
            if "agents" in new_config:
                for name, agent_config in new_config["agents"].items():
                    if name in self.config.agents:
                        for key, value in agent_config.items():
                            if hasattr(self.config.agents[name], key):
                                setattr(self.config.agents[name], key, value)

            # 保存配置
            save_agent_config(self.config)
            return True
        except Exception as e:
            print(f"[Orchestrator] 更新配置失败: {e}")
            return False

    def trigger_ceo_optimization(self, force: bool = False) -> Dict[str, Any]:
        """触发CEO优化"""
        # 收集各Agent的评估数据
        agents_evaluation = {}
        for name, agent in self.agents.items():
            agents_evaluation[name] = agent.get_evaluation()

        return self.ceo.execute({
            "force": force,
            "agents_evaluation": agents_evaluation,
        })

    def get_agent_capabilities(self) -> Dict[str, List[str]]:
        """获取所有Agent的能力"""
        capabilities = {}
        for name, agent in self.agents.items():
            capabilities[name] = agent.get_capabilities()
        return capabilities


# 全局单例
_orchestrator: Optional[SystemOrchestrator] = None


def get_orchestrator() -> SystemOrchestrator:
    """获取系统编排器单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SystemOrchestrator()
    return _orchestrator
