import time
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Set, Dict, Any, Callable

from app.database import SessionLocal
from app.services.event_service import EventService
from app.services.sse_manager import get_sse_manager
from app.services.trigger_service import TriggerManager
from app.models import Status, Event, TriggerType, Trigger


class ReminderEngine:
    """提醒引擎 - 处理事件提醒和完成度询问"""

    def __init__(self):
        self.event_service = EventService()
        self._running = False
        self._thread = None
        self._sse_manager = get_sse_manager()
        self._trigger_mgr = TriggerManager()
        self._notified_events: Set[int] = set()  # 已提醒的事件ID
        self._asked_events: Set[int] = set()     # 已询问完成度的事件ID
        self._executed_triggers: Set[int] = set()  # 今日已执行的触发器ID
        self.db = SessionLocal()
        self._trigger_handlers: Dict[TriggerType, Callable] = {
            TriggerType.event_start: self._handle_event_start_trigger,
            TriggerType.event_end: self._handle_event_end_trigger,
            TriggerType.daily_morning: self._handle_daily_morning_trigger,
            TriggerType.daily_evening: self._handle_daily_evening_trigger,
        }

    def start(self, interval_seconds: int = 10):
        """启动提醒引擎后台循环"""
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, args=(interval_seconds,), daemon=True
        )
        self._thread.start()
        print("[提醒引擎] 已启动，每 {}s 检查一次".format(interval_seconds))

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.event_service.close()
        self._trigger_mgr.close()
        self.db.close()
        print("[提醒引擎] 已停止")

    def _loop(self, interval_seconds: int):
        while self._running:
            try:
                now = datetime.now()
                # 每天午夜清理缓存
                if now.hour == 0 and now.minute == 0 and now.second < interval_seconds:
                    self.clear_caches()
                self._check_triggers(now)
                self._check_reminders()
                self._check_event_end()
            except Exception as e:
                print(f"[提醒引擎] 错误: {e}")
            time.sleep(interval_seconds)

    def _check_triggers(self, now: datetime):
        """检查触发器并执行到期的触发器"""
        try:
            due_triggers = self._trigger_mgr.get_due_triggers(now)
            for trigger in due_triggers:
                if trigger.id not in self._executed_triggers:
                    print(f"[提醒引擎] 执行触发器: {trigger.name}")
                    self._execute_trigger(trigger)
                    self._executed_triggers.add(trigger.id)
        except Exception as e:
            print(f"[提醒引擎] 检查触发器失败: {e}")

    def _execute_trigger(self, trigger: Trigger):
        """执行触发器"""
        try:
            trigger_type = TriggerType(trigger.trigger_type)
            handler = self._trigger_handlers.get(trigger_type)
            if handler:
                handler(trigger)
            else:
                print(f"[提醒引擎] 未知触发器类型: {trigger_type}")
        except Exception as e:
            print(f"[提醒引擎] 执行触发器失败: {e}")

    def _handle_event_start_trigger(self, trigger: Trigger):
        """处理事件开始提醒触发器"""
        config = self._trigger_mgr.get_config(trigger)
        event_id = trigger.event_id
        if event_id:
            event = self.db.query(Event).filter(Event.id == event_id).first()
            if event:
                minutes_left = config.get("minutes_before", 10)
                self._notify_start_reminder(event, timedelta(minutes=minutes_left))

    def _handle_event_end_trigger(self, trigger: Trigger):
        """处理事件结束询问触发器"""
        event_id = trigger.event_id
        if event_id:
            event = self.db.query(Event).filter(Event.id == event_id).first()
            if event:
                self._ask_completion(event)

    def _handle_daily_morning_trigger(self, trigger: Trigger):
        """处理每日凌晨规划触发器"""
        print("[提醒引擎] 每日凌晨规划触发器触发")
        # 通过 SSE 发送通知，前端可以选择处理
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._sse_manager.broadcast("system", {
                    "type": "daily_morning",
                    "message": "每日规划时间到了",
                    "trigger_id": trigger.id,
                })
            )
            loop.close()
        except Exception as e:
            print(f"[提醒引擎] SSE推送失败: {e}")

    def _handle_daily_evening_trigger(self, trigger: Trigger):
        """处理每日晚间总结触发器"""
        print("[提醒引擎] 每日晚间总结触发器触发")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._sse_manager.broadcast("system", {
                    "type": "daily_evening",
                    "message": "每日总结时间到了",
                    "trigger_id": trigger.id,
                })
            )
            loop.close()
        except Exception as e:
            print(f"[提醒引擎] SSE推送失败: {e}")

    def _check_reminders(self):
        """检查需要提前提醒的事件（前十分钟）"""
        now = datetime.now()
        check_window_start = now
        check_window_end = now + timedelta(minutes=10)

        # 获取今日待处理事件
        from sqlalchemy import func
        events = self.db.query(Event).filter(
            func.date(Event.start_time) == now.date(),
            Event.status.in_([Status.pending, Status.active]),
        ).all()

        for event in events:
            # 检查是否在前十分钟窗口内
            time_until_start = event.start_time - now
            if timedelta(minutes=0) <= time_until_start <= timedelta(minutes=10):
                if event.id not in self._notified_events:
                    self._notify_start_reminder(event, time_until_start)
                    self._notified_events.add(event.id)

            # 检查是否刚到开始时间
            if event.start_time <= now < event.end_time:
                if event.status == Status.pending:
                    event.status = Status.active
                    self.db.commit()

    def _check_event_end(self):
        """检查已结束的事件，询问完成度"""
        now = datetime.now()

        from sqlalchemy import func
        events = self.db.query(Event).filter(
            func.date(Event.end_time) == now.date(),
            Event.end_time <= now,
            Event.status == Status.active,
        ).all()

        for event in events:
            if event.id not in self._asked_events:
                self._ask_completion(event)
                self._asked_events.add(event.id)

    def _notify_start_reminder(self, event: Event, time_until_start: timedelta):
        """发送事件开始提醒"""
        minutes_left = int(time_until_start.total_seconds() // 60)

        # 终端通知
        bell = "\a"
        print(f"\n{'='*50}")
        print(f"{bell} [日程提醒] {event.title}")
        print(f"    还有 {minutes_left} 分钟开始")
        if event.description:
            print(f"    {event.description}")
        print(f"    开始时间: {event.start_time.strftime('%H:%M')}")
        print(f"    结束时间: {event.end_time.strftime('%H:%M')}")
        print(f"    优先级:   {event.priority.value}")
        print(f"{'='*50}\n")

        # SSE 推送到前端
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._sse_manager.broadcast("reminder", {
                    "type": "pre_reminder",
                    "id": event.id,
                    "title": event.title,
                    "description": event.description,
                    "start_time": event.start_time.strftime("%H:%M"),
                    "end_time": event.end_time.strftime("%H:%M"),
                    "priority": event.priority.value,
                    "minutes_left": minutes_left,
                })
            )
            loop.close()
        except Exception as e:
            print(f"[提醒引擎] SSE推送失败: {e}")

    def _ask_completion(self, event: Event):
        """询问事件完成度"""
        print(f"\n{'='*50}")
        print(f"[完成度询问] {event.title} 已结束")
        print(f"    请评估完成情况")
        print(f"{'='*50}\n")

        # SSE 推送到前端
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._sse_manager.broadcast("completion_ask", {
                    "type": "completion_ask",
                    "id": event.id,
                    "title": event.title,
                    "description": event.description,
                    "start_time": event.start_time.strftime("%H:%M"),
                    "end_time": event.end_time.strftime("%H:%M"),
                })
            )
            loop.close()
        except Exception as e:
            print(f"[提醒引擎] SSE推送失败: {e}")

    def _notify(self, event):
        """旧版通知方法 - 保留兼容"""
        self._notify_start_reminder(event, timedelta(minutes=0))

    def clear_caches(self):
        """清理缓存（每天午夜调用）"""
        self._notified_events.clear()
        self._asked_events.clear()
        self._executed_triggers.clear()
        print("[提醒引擎] 缓存已清理")
