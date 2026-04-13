import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Priority(str, enum.Enum):
    urgent = "urgent"
    high = "high"
    medium = "medium"
    low = "low"


class Status(str, enum.Enum):
    pending = "pending"
    active = "active"
    completed = "completed"
    skipped = "skipped"


class Channel(str, enum.Enum):
    desktop = "desktop"
    web = "web"


class TriggerType(str, enum.Enum):
    event_start = "event_start"       # 事件开始前提醒
    event_end = "event_end"           # 事件结束后询问
    daily_morning = "daily_morning"   # 每日凌晨规划
    daily_evening = "daily_evening"   # 每日晚间总结
    custom = "custom"                  # 自定义触发器


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    priority = Column(Enum(Priority), default=Priority.medium)
    status = Column(Enum(Status), default=Status.pending)
    is_ai_scheduled = Column(Boolean, default=False)
    is_split_task = Column(Boolean, default=False)  # 是否是拆分的子任务
    parent_task_title = Column(String(200), default="")  # 父任务标题
    created_at = Column(DateTime, default=datetime.now)

    # 新增字段：详细信息
    location = Column(String(500), default="")  # 地点
    participants = Column(Text, default="")  # 参与人员（JSON 数组）
    task_steps = Column(Text, default="")  # 任务流程/步骤（JSON 数组）
    notes = Column(Text, default="")  # 备注
    category = Column(String(100), default="")  # 分类：work, personal, meeting, exercise, etc.
    recurrence = Column(String(100), default="")  # 重复规则

    reminders = relationship("Reminder", back_populates="event", cascade="all, delete-orphan")
    summaries = relationship("EventSummary", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Event {self.title} [{self.priority.value}] {self.start_time}>"


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    trigger_time = Column(DateTime, nullable=False)
    reminder_type = Column(String(20), default="pre")  # pre: 提前提醒, post: 结束询问
    notified = Column(Boolean, default=False)
    channel = Column(Enum(Channel), default=Channel.desktop)

    event = relationship("Event", back_populates="reminders")


class DayPlan(Base):
    __tablename__ = "day_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, unique=True)
    ai_summary = Column(Text, default="")
    detailed_plan = Column(Text, default="")  # 详细规划 JSON
    is_auto_generated = Column(Boolean, default=False)  # 是否自动生成
    created_at = Column(DateTime, default=datetime.now)

    notes = relationship("Note", back_populates="day_plan", cascade="all, delete-orphan")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), nullable=False, unique=True)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<UserPreference {self.key}={self.value}>"


class Trigger(Base):
    """触发器表 - 管理自动触发的任务"""
    __tablename__ = "triggers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    trigger_type = Column(Enum(TriggerType), default=TriggerType.custom)
    trigger_time = Column(String(10))  # HH:MM 格式，用于定时触发器
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    is_enabled = Column(Boolean, default=True)
    config = Column(Text, default="")  # JSON 配置
    created_at = Column(DateTime, default=datetime.now)

    event = relationship("Event")


class EventSummary(Base):
    """事件总结 - 记录每个事件的完成情况和总结"""
    __tablename__ = "event_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    completion_rate = Column(Integer, default=0)  # 0-100 完成度
    summary = Column(Text, default="")  # 事件总结
    reflection = Column(Text, default="")  # 反思/收获
    obstacles = Column(Text, default="")  # 遇到的困难
    created_at = Column(DateTime, default=datetime.now)

    event = relationship("Event", back_populates="summaries")


class Note(Base):
    """记事板 - 整理规划过程和事件总结"""
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, index=True)  # 关联日期
    day_plan_id = Column(Integer, ForeignKey("day_plans.id"), nullable=True)
    note_type = Column(String(20), default="general")  # general, plan, summary, reflection
    title = Column(String(200), default="")
    content = Column(Text, default="")
    tags = Column(String(500), default="")  # 逗号分隔的标签
    is_ai_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    day_plan = relationship("DayPlan", back_populates="notes")


class DailySummary(Base):
    """每日总结 - 完整的一天总结"""
    __tablename__ = "daily_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, unique=True)
    overall_summary = Column(Text, default="")  # 整体总结
    completion_rate = Column(Integer, default=0)  # 今日完成率
    highlights = Column(Text, default="")  # 亮点 JSON
    improvements = Column(Text, default="")  # 改进建议 JSON
    tomorrow_plan = Column(Text, default="")  # 明日规划 JSON
    created_at = Column(DateTime, default=datetime.now)


class Recipe(Base):
    """食谱"""
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)  # 食谱名称
    description = Column(Text, default="")  # 描述
    ingredients = Column(Text, default="")  # 食材 JSON
    instructions = Column(Text, default="")  # 步骤 JSON
    prep_time = Column(Integer, default=0)  # 准备时间(分钟)
    cook_time = Column(Integer, default=0)  # 烹饪时间(分钟)
    servings = Column(Integer, default=2)  # 份量
    difficulty = Column(String(20), default="medium")  # easy/medium/hard
    tags = Column(Text, default="")  # 标签逗号分隔
    cuisine = Column(String(50), default="")  # 菜系
    meal_type = Column(String(20), default="dinner")  # breakfast/lunch/dinner/snack

    # 营养信息
    calories = Column(Integer, default=0)  # 卡路里
    protein = Column(Integer, default=0)  # 蛋白质(克)
    carbs = Column(Integer, default=0)  # 碳水(克)
    fat = Column(Integer, default=0)  # 脂肪(克)
    fiber = Column(Integer, default=0)  # 膳食纤维(克)

    is_custom = Column(Boolean, default=False)  # 是否用户自定义
    created_at = Column(DateTime, default=datetime.now)


class MealPlan(Base):
    """每周饮食计划"""
    __tablename__ = "meal_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    week_start = Column(String(10), nullable=False)  # 周一日期 YYYY-MM-DD
    plan_data = Column(Text, default="")  # 计划 JSON {day: {meal: recipe_id}}
    notes = Column(Text, default="")  # 备注
    created_at = Column(DateTime, default=datetime.now)

