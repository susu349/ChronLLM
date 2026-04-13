"""
Agent配置管理
支持前端可视化配置每个Agent的参数、开关、权重等
"""
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from pathlib import Path


@dataclass
class AgentConfig:
    """单个Agent的配置"""
    name: str
    enabled: bool = True
    priority: int = 5  # 1-10, 越高越优先
    weight: float = 1.0  # 决策权重
    max_retries: int = 3
    circuit_break_threshold: int = 5
    timeout: int = 30  # seconds
    fallback_enabled: bool = True
    risk_transfer_enabled: bool = True
    risk_transfer_target: Optional[str] = None
    custom_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentConfig':
        return cls(**data)


@dataclass
class SystemConfig:
    """整个多智能体系统的配置"""
    agents: Dict[str, AgentConfig] = field(default_factory=dict)
    supervisor_config: Dict[str, Any] = field(default_factory=dict)
    ceo_config: Dict[str, Any] = field(default_factory=dict)
    global_settings: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            from datetime import datetime
            self.created_at = datetime.now().isoformat()
        if not self.global_settings:
            self.global_settings = {
                "ceo_optimization_interval_days": 10,
                "behavior_compression_hour": 23,
                "context_max_tokens": 8000,
                "auto_audit_enabled": True,
                "nested_evaluation_depth": 3,
            }
        if not self.supervisor_config:
            self.supervisor_config = {
                "orchestration_strategy": "priority_based",
                "max_concurrent_agents": 3,
                "conflict_resolution": "priority_first",
            }
        if not self.ceo_config:
            self.ceo_config = {
                "optimization_enabled": True,
                "learning_rate": 0.1,
                "exploration_rate": 0.2,
            }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agents": {name: cfg.to_dict() for name, cfg in self.agents.items()},
            "supervisor_config": self.supervisor_config,
            "ceo_config": self.ceo_config,
            "global_settings": self.global_settings,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemConfig':
        agents = {
            name: AgentConfig.from_dict(cfg)
            for name, cfg in data.get("agents", {}).items()
        }
        return cls(
            agents=agents,
            supervisor_config=data.get("supervisor_config", {}),
            ceo_config=data.get("ceo_config", {}),
            global_settings=data.get("global_settings", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


# 默认Agent配置
DEFAULT_AGENT_CONFIGS = {
    "main": AgentConfig(
        name="main",
        priority=10,
        weight=1.0,
    ),
    "planning": AgentConfig(
        name="planning",
        priority=9,
        weight=0.9,
    ),
    "task_decomposition": AgentConfig(
        name="task_decomposition",
        priority=8,
        weight=0.8,
    ),
    "chef": AgentConfig(
        name="chef",
        priority=7,
        weight=0.8,
    ),
    "event_handler": AgentConfig(
        name="event_handler",
        priority=8,
        weight=0.9,
    ),
    "weather": AgentConfig(
        name="weather",
        priority=6,
        weight=0.7,
    ),
    "audit": AgentConfig(
        name="audit",
        priority=9,
        weight=1.0,
    ),
    "behavior_compression": AgentConfig(
        name="behavior_compression",
        priority=5,
        weight=0.6,
    ),
    "context_compression": AgentConfig(
        name="context_compression",
        priority=7,
        weight=0.7,
    ),
    "supervisor": AgentConfig(
        name="supervisor",
        priority=10,
        weight=1.0,
    ),
    "ceo": AgentConfig(
        name="ceo",
        priority=10,
        weight=1.0,
    ),
}


# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "data"
CONFIG_FILE = CONFIG_DIR / "multi_agent_config.json"


def get_agent_config() -> SystemConfig:
    """获取系统配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return SystemConfig.from_dict(data)
        except Exception as e:
            print(f"[AgentConfig] 加载配置失败: {e}")

    # 创建默认配置
    config = SystemConfig()
    config.agents = {
        name: cfg for name, cfg in DEFAULT_AGENT_CONFIGS.items()
    }
    save_agent_config(config)
    return config


def save_agent_config(config: SystemConfig) -> bool:
    """保存系统配置"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        config.updated_at = datetime.now().isoformat()
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[AgentConfig] 保存配置失败: {e}")
        return False


def get_agent_config_schema() -> Dict[str, Any]:
    """获取配置Schema（用于前端渲染配置界面）"""
    return {
        "global_settings": {
            "ceo_optimization_interval_days": {
                "type": "number",
                "label": "CEO优化间隔（天）",
                "min": 1,
                "max": 30,
                "default": 10,
            },
            "behavior_compression_hour": {
                "type": "number",
                "label": "行为压缩执行时间（小时）",
                "min": 0,
                "max": 23,
                "default": 23,
            },
            "context_max_tokens": {
                "type": "number",
                "label": "上下文最大Token数",
                "min": 1000,
                "max": 32000,
                "default": 8000,
            },
            "auto_audit_enabled": {
                "type": "boolean",
                "label": "启用自动审计",
                "default": True,
            },
            "nested_evaluation_depth": {
                "type": "number",
                "label": "嵌套评估深度",
                "min": 1,
                "max": 5,
                "default": 3,
            },
        },
        "agents": {
            "main": {
                "label": "主Agent",
                "description": "处理用户问题并进行编排并调用工具",
                "params": [],
            },
            "planning": {
                "label": "规划Agent",
                "description": "每日任务和历史任务和未来规划对齐",
                "params": [],
            },
            "task_decomposition": {
                "label": "任务拆解Agent",
                "description": "拆解大任务并进入事件处理区",
                "params": [],
            },
            "chef": {
                "label": "厨师Agent",
                "description": "规划每日菜单和菜单推荐（越精细越好）",
                "params": [
                    {
                        "name": "cuisine_preference",
                        "type": "select",
                        "label": "菜系偏好",
                        "options": ["川菜", "粤菜", "湘菜", "鲁菜", "苏菜", "浙菜", "闽菜", "徽菜", "西餐", "日料", "韩餐", "任意"],
                        "default": "任意",
                    },
                    {
                        "name": "spicy_level",
                        "type": "number",
                        "label": "辣度（0-5）",
                        "min": 0,
                        "max": 5,
                        "default": 2,
                    },
                    {
                        "name": "meal_count",
                        "type": "number",
                        "label": "每日餐数",
                        "min": 2,
                        "max": 6,
                        "default": 3,
                    },
                ],
            },
            "event_handler": {
                "label": "事件处理Agent",
                "description": "处理任务处理区事件",
                "params": [],
            },
            "weather": {
                "label": "天气Agent",
                "description": "查询天气并生成说明",
                "params": [
                    {
                        "name": "location",
                        "type": "text",
                        "label": "默认城市",
                        "default": "北京",
                    },
                ],
            },
            "audit": {
                "label": "审计Agent",
                "description": "每一步规划是否合理",
                "params": [
                    {
                        "name": "strictness",
                        "type": "number",
                        "label": "审计严格度（0-10）",
                        "min": 0,
                        "max": 10,
                        "default": 7,
                    },
                ],
            },
            "behavior_compression": {
                "label": "行为压缩Agent",
                "description": "每天更新行为和记录异常值",
                "params": [],
            },
            "context_compression": {
                "label": "上下文压缩Agent",
                "description": "加载用户身份状态、行为惯性、近期行为",
                "params": [],
            },
        },
    }
