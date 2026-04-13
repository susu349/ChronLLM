import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field


@dataclass
class ConversationStep:
    """对话步骤"""
    id: str
    question: str
    answer: Optional[str] = None
    answered_at: Optional[datetime] = None


@dataclass
class CollectedInfo:
    """收集到的信息"""
    # 基本信息
    user_name: str = ""
    mood: str = ""

    # 今日目标
    main_goal: str = ""
    top_priorities: List[str] = field(default_factory=list)

    # 工作/学习
    work_tasks: List[str] = field(default_factory=list)
    work_hours: str = ""

    # 生活安排
    meals: List[Dict] = field(default_factory=list)
    exercise: str = ""
    exercise_time: str = ""

    # 社交
    meetings: List[Dict] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)

    # 其他
    errands: List[str] = field(default_factory=list)
    relax_activities: List[str] = field(default_factory=list)

    # 时间偏好
    morning_energy: str = ""  # high/medium/low
    evening_energy: str = ""  # high/medium/low

    # 特殊事项
    urgent_tasks: List[str] = field(default_factory=list)
    reminders: List[str] = field(default_factory=list)


class ConversationState:
    """对话状态管理"""

    # 对话流程步骤
    STEPS = [
        {
            "id": "greeting",
            "question": "早上好！新的一天开始了，今天感觉怎么样？",
        },
        {
            "id": "main_goal",
            "question": "好的！今天最想完成的一件事是什么？",
        },
        {
            "id": "work_tasks",
            "question": "工作/学习方面有什么需要做的吗？",
        },
        {
            "id": "meetings",
            "question": "今天有会议或者约会需要安排吗？",
        },
        {
            "id": "exercise",
            "question": "今天要不要安排运动时间？如果需要，想做什么运动？",
        },
        {
            "id": "urgent",
            "question": "有什么特别紧急或者重要的事需要提醒吗？",
        },
        {
            "id": "relax",
            "question": "好的！最后，有什么想做的放松活动吗？",
        },
    ]

    def __init__(self):
        self.current_step_index: int = 0
        self.steps: List[ConversationStep] = []
        self.info: CollectedInfo = CollectedInfo()
        self.started_at: datetime = datetime.now()
        self.is_active: bool = False
        self.is_finished: bool = False

        # 初始化步骤
        for step_def in self.STEPS:
            self.steps.append(ConversationStep(
                id=step_def["id"],
                question=step_def["question"]
            ))

    def start(self) -> str:
        """开始对话，返回第一个问题"""
        self.is_active = True
        self.current_step_index = 0
        return self.get_current_question()

    def get_current_question(self) -> Optional[str]:
        """获取当前问题"""
        if self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index].question
        return None

    def answer(self, text: str) -> Optional[str]:
        """回答当前问题，返回下一个问题或 None（结束）"""
        if not self.is_active or self.is_finished:
            return None

        # 保存答案
        if self.current_step_index < len(self.steps):
            step = self.steps[self.current_step_index]
            step.answer = text
            step.answered_at = datetime.now()
            self._extract_info(step.id, text)

        # 移动到下一步
        self.current_step_index += 1

        if self.current_step_index >= len(self.steps):
            self.is_finished = True
            self.is_active = False
            return None

        return self.get_current_question()

    def _extract_info(self, step_id: str, text: str):
        """从回答中提取信息"""
        text_lower = text.lower()

        if step_id == "greeting":
            if "好" in text or "开心" in text or "棒" in text:
                self.info.mood = "good"
            elif "累" in text or "困" in text or "糟" in text:
                self.info.mood = "tired"
            else:
                self.info.mood = "normal"

        elif step_id == "main_goal":
            self.info.main_goal = text
            if "重要" in text or "紧急" in text:
                self.info.urgent_tasks.append(text)

        elif step_id == "work_tasks":
            if "没有" not in text and "无" not in text:
                # 简单分割多个任务
                tasks = [t.strip() for t in text.replace("；", ";").replace("，", ",").split(";")]
                tasks = [t for t in tasks if t]
                if not tasks:
                    tasks = [text]
                self.info.work_tasks = tasks

        elif step_id == "meetings":
            if "没有" not in text and "无" not in text:
                self.info.meetings.append({"description": text})

        elif step_id == "exercise":
            if "不" not in text and "不要" not in text and "没有" not in text:
                self.info.exercise = text
                if "早上" in text or "上午" in text:
                    self.info.exercise_time = "morning"
                elif "晚上" in text or "下午" in text:
                    self.info.exercise_time = "evening"
                else:
                    self.info.exercise_time = "evening"

        elif step_id == "urgent":
            if "没有" not in text and "无" not in text:
                self.info.urgent_tasks.append(text)

        elif step_id == "relax":
            if "没有" not in text and "无" not in text:
                activities = [a.strip() for a in text.replace("；", ";").replace("，", ",").split(";")]
                activities = [a for a in activities if a]
                if not activities:
                    activities = [text]
                self.info.relax_activities = activities

    def get_summary(self) -> Dict[str, Any]:
        """获取收集到的信息摘要"""
        return {
            "steps": [
                {"id": s.id, "question": s.question, "answer": s.answer}
                for s in self.steps
            ],
            "info": asdict(self.info),
            "is_finished": self.is_finished,
        }

    def reset(self):
        """重置状态"""
        self.__init__()


# 全局会话状态（简化版 - 实际生产可改用 Redis）
_conversations: Dict[str, ConversationState] = {}


def get_conversation(session_id: str = "default") -> ConversationState:
    """获取会话状态"""
    if session_id not in _conversations:
        _conversations[session_id] = ConversationState()
    return _conversations[session_id]


def reset_conversation(session_id: str = "default"):
    """重置会话"""
    if session_id in _conversations:
        del _conversations[session_id]
