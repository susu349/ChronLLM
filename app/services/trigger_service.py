import json
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional, Callable

from app.database import SessionLocal
from app.models import Trigger, TriggerType, Event


class TriggerManager:
    """触发器管理器"""

    def __init__(self):
        self.db = SessionLocal()
        self._callbacks: Dict[str, Callable] = {}

    def close(self):
        self.db.close()

    # ============ Trigger CRUD ============

    def create_trigger(
        self,
        name: str,
        trigger_type: TriggerType,
        trigger_time: str = None,
        event_id: int = None,
        config: Dict = None,
        is_enabled: bool = True,
    ) -> Trigger:
        """创建触发器"""
        trigger = Trigger(
            name=name,
            trigger_type=trigger_type,
            trigger_time=trigger_time,
            event_id=event_id,
            config=json.dumps(config, ensure_ascii=False) if config else "{}",
            is_enabled=is_enabled,
        )
        self.db.add(trigger)
        self.db.commit()
        self.db.refresh(trigger)
        return trigger

    def get_trigger(self, trigger_id: int) -> Optional[Trigger]:
        """获取触发器"""
        return self.db.query(Trigger).filter(Trigger.id == trigger_id).first()

    def get_triggers_by_type(self, trigger_type: TriggerType, only_enabled: bool = True) -> List[Trigger]:
        """按类型获取触发器"""
        query = self.db.query(Trigger).filter(Trigger.trigger_type == trigger_type)
        if only_enabled:
            query = query.filter(Trigger.is_enabled == True)
        return query.all()

    def get_all_triggers(self, only_enabled: bool = False) -> List[Trigger]:
        """获取所有触发器"""
        query = self.db.query(Trigger)
        if only_enabled:
            query = query.filter(Trigger.is_enabled == True)
        return query.order_by(Trigger.created_at.desc()).all()

    def update_trigger(
        self,
        trigger_id: int,
        name: str = None,
        trigger_time: str = None,
        is_enabled: bool = None,
        config: Dict = None,
    ) -> Optional[Trigger]:
        """更新触发器"""
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            return None
        if name is not None:
            trigger.name = name
        if trigger_time is not None:
            trigger.trigger_time = trigger_time
        if is_enabled is not None:
            trigger.is_enabled = is_enabled
        if config is not None:
            trigger.config = json.dumps(config, ensure_ascii=False)
        self.db.commit()
        self.db.refresh(trigger)
        return trigger

    def delete_trigger(self, trigger_id: int) -> bool:
        """删除触发器"""
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            return False
        self.db.delete(trigger)
        self.db.commit()
        return True

    def toggle_trigger(self, trigger_id: int) -> Optional[Trigger]:
        """切换触发器启用状态"""
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            return None
        trigger.is_enabled = not trigger.is_enabled
        self.db.commit()
        self.db.refresh(trigger)
        return trigger

    # ============ Event Reminder Triggers ============

    def create_event_reminder_trigger(self, event: Event, minutes_before: int = 10) -> Trigger:
        """为事件创建提前提醒触发器"""
        trigger_time = event.start_time - timedelta(minutes=minutes_before)
        return self.create_trigger(
            name=f"{event.title} - 提前提醒",
            trigger_type=TriggerType.event_start,
            trigger_time=trigger_time.strftime("%H:%M"),
            event_id=event.id,
            config={
                "minutes_before": minutes_before,
                "event_title": event.title,
                "trigger_at": trigger_time.isoformat(),
            },
        )

    def create_event_end_trigger(self, event: Event) -> Trigger:
        """为事件创建结束询问触发器"""
        return self.create_trigger(
            name=f"{event.title} - 完成度询问",
            trigger_type=TriggerType.event_end,
            trigger_time=event.end_time.strftime("%H:%M"),
            event_id=event.id,
            config={
                "event_title": event.title,
                "trigger_at": event.end_time.isoformat(),
            },
        )

    # ============ Daily Triggers ============

    def setup_default_triggers(self):
        """设置默认触发器"""
        # 检查是否已存在
        existing_morning = self.db.query(Trigger).filter(
            Trigger.trigger_type == TriggerType.daily_morning
        ).first()

        if not existing_morning:
            self.create_trigger(
                name="每日凌晨规划",
                trigger_type=TriggerType.daily_morning,
                trigger_time="00:30",
                config={
                    "description": "每天凌晨00:30生成当天的规划和前一天的总结",
                },
            )
            print("[触发器] 已创建每日凌晨规划触发器")

        existing_evening = self.db.query(Trigger).filter(
            Trigger.trigger_type == TriggerType.daily_evening
        ).first()

        if not existing_evening:
            self.create_trigger(
                name="每日晚间总结",
                trigger_type=TriggerType.daily_evening,
                trigger_time="23:30",
                config={
                    "description": "每天晚上23:30生成当日总结",
                },
            )
            print("[触发器] 已创建每日晚间总结触发器")

    def get_daily_morning_trigger(self) -> Optional[Trigger]:
        """获取每日凌晨规划触发器"""
        return self.db.query(Trigger).filter(
            Trigger.trigger_type == TriggerType.daily_morning
        ).first()

    def get_daily_evening_trigger(self) -> Optional[Trigger]:
        """获取每日晚间总结触发器"""
        return self.db.query(Trigger).filter(
            Trigger.trigger_type == TriggerType.daily_evening
        ).first()

    # ============ Check Triggers ============

    def get_due_triggers(self, check_time: datetime = None) -> List[Trigger]:
        """获取到期需要执行的触发器"""
        if check_time is None:
            check_time = datetime.now()

        time_str = check_time.strftime("%H:%M")
        date_str = check_time.date().isoformat()

        due_triggers = []

        # 检查定时触发器
        enabled_triggers = self.get_all_triggers(only_enabled=True)
        for trigger in enabled_triggers:
            if trigger.trigger_time == time_str:
                due_triggers.append(trigger)

        return due_triggers

    def get_config(self, trigger: Trigger) -> Dict:
        """获取触发器配置"""
        if trigger.config:
            try:
                return json.loads(trigger.config)
            except json.JSONDecodeError:
                pass
        return {}

    def to_dict(self, trigger: Trigger) -> Dict[str, Any]:
        """转换触发器为字典"""
        return {
            "id": trigger.id,
            "name": trigger.name,
            "trigger_type": trigger.trigger_type.value,
            "trigger_time": trigger.trigger_time,
            "event_id": trigger.event_id,
            "is_enabled": trigger.is_enabled,
            "config": self.get_config(trigger),
            "created_at": trigger.created_at.isoformat() if trigger.created_at else None,
        }
