"""
Agent记忆系统
为每个Agent提供独立的记忆存储，支持：
- 短期记忆（对话上下文）
- 长期记忆（用户习惯、偏好、历史行为）
- 边界记忆（Agent职责边界）
"""
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum


class MemoryType(Enum):
    """记忆类型"""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    BOUNDARY = "boundary"
    EPISODIC = "episodic"


@dataclass
class MemoryItem:
    """记忆条目"""
    memory_id: str
    memory_type: str
    content: Dict[str, Any]
    timestamp: str
    importance: float = 0.5  # 0.0-1.0
    tags: List[str] = field(default_factory=list)
    expires_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryItem':
        return cls(**data)


class AgentMemory:
    """单个Agent的记忆系统"""

    def __init__(self, agent_name: str, storage_dir: Path = None):
        self.agent_name = agent_name
        self.storage_dir = storage_dir or Path(__file__).parent.parent.parent / "data" / "agent_memory"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.short_term: List[MemoryItem] = []
        self.long_term: List[MemoryItem] = []
        self.boundary: Dict[str, Any] = {}
        self.episodic: List[MemoryItem] = []

        self._load_memory()
        self._init_default_boundary()

    def _get_memory_file(self) -> Path:
        """获取记忆文件路径"""
        return self.storage_dir / f"{self.agent_name}_memory.json"

    def _load_memory(self):
        """从文件加载记忆"""
        memory_file = self._get_memory_file()
        if memory_file.exists():
            try:
                with open(memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.short_term = [MemoryItem.from_dict(item) for item in data.get('short_term', [])]
                    self.long_term = [MemoryItem.from_dict(item) for item in data.get('long_term', [])]
                    self.boundary = data.get('boundary', {})
                    self.episodic = [MemoryItem.from_dict(item) for item in data.get('episodic', [])]
            except Exception as e:
                print(f"[AgentMemory] 加载记忆失败: {e}")

    def _save_memory(self):
        """保存记忆到文件"""
        memory_file = self._get_memory_file()
        data = {
            'short_term': [item.to_dict() for item in self.short_term],
            'long_term': [item.to_dict() for item in self.long_term],
            'boundary': self.boundary,
            'episodic': [item.to_dict() for item in self.episodic],
        }
        try:
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AgentMemory] 保存记忆失败: {e}")

    def _init_default_boundary(self):
        """初始化默认边界"""
        default_boundaries = {
            'main': {
                'role': '主Agent',
                'responsibilities': [
                    '理解用户意图',
                    '路由到专业Agent',
                    '协调多Agent协作',
                    '生成最终回复',
                ],
                'boundaries': [
                    '不直接处理规划细节',
                    '不直接生成菜单',
                    '不直接查询天气',
                ],
            },
            'planning': {
                'role': '规划Agent',
                'responsibilities': [
                    '生成每日规划',
                    '对齐历史任务',
                    '对齐未来规划',
                    '时间冲突检测',
                ],
                'boundaries': [
                    '不处理烹饪细节',
                    '不处理天气查询',
                ],
                'needs': ['weather', 'chef'],  # 依赖的其他Agent
            },
            'chef': {
                'role': '厨师Agent',
                'responsibilities': [
                    '推荐每日菜单',
                    '营养搭配建议',
                    '生成购物清单',
                    '烹饪技巧指导',
                ],
                'boundaries': [
                    '不处理日程规划',
                    '不处理非饮食问题',
                ],
            },
            'weather': {
                'role': '天气Agent',
                'responsibilities': [
                    '查询天气信息',
                    '生成出行建议',
                    '穿搭推荐',
                ],
                'boundaries': [
                    '不处理非天气问题',
                ],
            },
            'audit': {
                'role': '审计Agent',
                'responsibilities': [
                    '检查规划合理性',
                    '时间冲突检测',
                    '任务密度评估',
                    '优化建议生成',
                ],
                'boundaries': [
                    '不修改用户规划',
                    '只提供建议和检查',
                ],
            },
        }

        if not self.boundary and self.agent_name in default_boundaries:
            self.boundary = default_boundaries[self.agent_name]
            self._save_memory()

    def _generate_id(self, content: Dict[str, Any]) -> str:
        """生成记忆ID"""
        content_str = json.dumps(content, sort_keys=True) + datetime.now().isoformat()
        return hashlib.md5(content_str.encode()).hexdigest()[:12]

    def add_short_term(self, content: Dict[str, Any], tags: List[str] = None,
                      importance: float = 0.5, ttl_minutes: int = 60):
        """添加短期记忆"""
        item = MemoryItem(
            memory_id=self._generate_id(content),
            memory_type=MemoryType.SHORT_TERM.value,
            content=content,
            timestamp=datetime.now().isoformat(),
            importance=importance,
            tags=tags or [],
            expires_at=(datetime.now() + timedelta(minutes=ttl_minutes)).isoformat() if ttl_minutes else None,
        )
        self.short_term.insert(0, item)
        self.short_term = self.short_term[:50]  # 最多保留50条
        self._clean_expired()
        self._save_memory()
        return item

    def add_long_term(self, content: Dict[str, Any], tags: List[str] = None,
                     importance: float = 0.7):
        """添加长期记忆"""
        item = MemoryItem(
            memory_id=self._generate_id(content),
            memory_type=MemoryType.LONG_TERM.value,
            content=content,
            timestamp=datetime.now().isoformat(),
            importance=importance,
            tags=tags or [],
        )
        self.long_term.insert(0, item)
        self.long_term = self.long_term[:200]  # 最多保留200条
        self._save_memory()
        return item

    def add_episodic(self, content: Dict[str, Any], tags: List[str] = None,
                    importance: float = 0.6):
        """添加情景记忆"""
        item = MemoryItem(
            memory_id=self._generate_id(content),
            memory_type=MemoryType.EPISODIC.value,
            content=content,
            timestamp=datetime.now().isoformat(),
            importance=importance,
            tags=tags or [],
        )
        self.episodic.insert(0, item)
        self.episodic = self.episodic[:100]  # 最多保留100条
        self._save_memory()
        return item

    def _clean_expired(self):
        """清理过期记忆"""
        now = datetime.now().isoformat()
        self.short_term = [
            item for item in self.short_term
            if item.expires_at is None or item.expires_at > now
        ]

    def retrieve(self, query: str = None, memory_type: MemoryType = None,
                 tags: List[str] = None, limit: int = 10) -> List[MemoryItem]:
        """检索记忆"""
        candidates = []

        if memory_type:
            if memory_type == MemoryType.SHORT_TERM:
                candidates = self.short_term
            elif memory_type == MemoryType.LONG_TERM:
                candidates = self.long_term
            elif memory_type == MemoryType.EPISODIC:
                candidates = self.episodic
        else:
            candidates = self.short_term + self.long_term + self.episodic

        if tags:
            candidates = [
                item for item in candidates
                if any(tag in item.tags for tag in tags)
            ]

        candidates.sort(key=lambda x: x.importance, reverse=True)
        return candidates[:limit]

    def get_boundary(self) -> Dict[str, Any]:
        """获取Agent边界"""
        return self.boundary

    def update_boundary(self, key: str, value: Any):
        """更新Agent边界"""
        self.boundary[key] = value
        self._save_memory()

    def get_user_preferences(self) -> Dict[str, Any]:
        """获取用户偏好（从长期记忆中）"""
        preferences = {}
        preference_items = self.retrieve(tags=['preference', 'user'], limit=20)
        for item in preference_items:
            preferences.update(item.content)
        return preferences

    def remember_user_preference(self, key: str, value: Any):
        """记住用户偏好"""
        self.add_long_term(
            content={key: value},
            tags=['preference', 'user', key],
            importance=0.8
        )

    def get_recent_context(self, limit: int = 5) -> List[Dict[str, Any]]:
        """获取最近对话上下文"""
        recent_items = self.short_term[:limit]
        return [item.content for item in recent_items]

    def clear_short_term(self):
        """清空短期记忆"""
        self.short_term = []
        self._save_memory()


# 全局记忆存储
_memory_instances: Dict[str, AgentMemory] = {}


def get_agent_memory(agent_name: str) -> AgentMemory:
    """获取指定Agent的记忆系统"""
    if agent_name not in _memory_instances:
        _memory_instances[agent_name] = AgentMemory(agent_name)
    return _memory_instances[agent_name]
