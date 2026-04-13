"""
多智能体系统 (Multi-Agent System)
核心架构：
- CEO Agent (优化者，10天一次)
- Supervisor Agent (主管，协调各Agent)
- 专业Agents:
  - Main Agent (主Agent，处理用户问题)
  - Planning Agent (规划Agent)
  - Task Decomposition Agent (任务拆解Agent)
  - Chef Agent (厨师Agent)
  - Event Handler Agent (事件处理Agent)
  - Weather Agent (天气Agent)
  - Audit Agent (审计Agent)
  - Behavior Compression Agent (行为压缩Agent)
  - Context Compression Agent (上下文压缩Agent)
"""
from .base_agent import BaseAgent, AgentStatus, AgentEvaluation
from .supervisor import SupervisorAgent
from .ceo_agent import CEOAgent
from .main_agent import MainAgent
from .planning_agent import (
    PlanningAgent,
    TaskDecompositionAgent,
    ChefAgent,
    EventHandlerAgent,
    WeatherAgent,
    AuditAgent,
    BehaviorCompressionAgent,
    ContextCompressionAgent,
)
from .agent_config import AgentConfig, SystemConfig, get_agent_config, save_agent_config, get_agent_config_schema
from .system_orchestrator import SystemOrchestrator, get_orchestrator

__all__ = [
    'BaseAgent',
    'AgentStatus',
    'AgentEvaluation',
    'SupervisorAgent',
    'CEOAgent',
    'MainAgent',
    'PlanningAgent',
    'TaskDecompositionAgent',
    'ChefAgent',
    'EventHandlerAgent',
    'WeatherAgent',
    'AuditAgent',
    'BehaviorCompressionAgent',
    'ContextCompressionAgent',
    'AgentConfig',
    'SystemConfig',
    'get_agent_config',
    'save_agent_config',
    'get_agent_config_schema',
    'SystemOrchestrator',
    'get_orchestrator',
]
