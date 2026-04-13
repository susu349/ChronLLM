import json
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.database import SessionLocal
from app.models import Event, Priority, Status, DayPlan
from app.services.preferences_service import PreferencesService
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


@dataclass
class ScheduleConflict:
    """日程冲突"""
    event1: Event
    event2: Event
    overlap_minutes: int


@dataclass
class AdjustmentSuggestion:
    """调整建议"""
    original_event: Event
    new_start_time: datetime
    new_end_time: datetime
    reason: str
    confidence: float


class SmartAdjuster:
    """智能日程调整器"""

    def __init__(self):
        self.db = SessionLocal()
        self.prefs = PreferencesService()

    def close(self):
        self.db.close()
        self.prefs.close()

    def detect_conflicts(self, target_date: date = None) -> List[ScheduleConflict]:
        """检测日程冲突"""
        if target_date is None:
            target_date = date.today()

        from sqlalchemy import func
        events = (
            self.db.query(Event)
            .filter(func.date(Event.start_time) == target_date)
            .filter(Event.status != Status.skipped)
            .order_by(Event.start_time)
            .all()
        )

        conflicts = []
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                e1, e2 = events[i], events[j]
                if self._has_overlap(e1, e2):
                    overlap = self._calculate_overlap(e1, e2)
                    conflicts.append(ScheduleConflict(e1, e2, overlap))

        return conflicts

    def _has_overlap(self, e1: Event, e2: Event) -> bool:
        """检查两个事件是否有重叠"""
        return not (e1.end_time <= e2.start_time or e2.end_time <= e1.start_time)

    def _calculate_overlap(self, e1: Event, e2: Event) -> int:
        """计算重叠时间（分钟）"""
        latest_start = max(e1.start_time, e2.start_time)
        earliest_end = min(e1.end_time, e2.end_time)
        delta = earliest_end - latest_start
        return int(delta.total_seconds() / 60)

    def suggest_adjustment(self, event: Event, events: List[Event]) -> Optional[AdjustmentSuggestion]:
        """为单个事件建议调整方案"""
        # 获取用户偏好
        prefs = self.prefs.get_all()
        buffer_minutes = int(prefs.get("buffer_minutes", "15"))

        # 找到可用的时间槽
        available_slots = self._find_available_slots(
            events, event.start_time.date(), buffer_minutes
        )

        # 找到最接近的可用槽
        event_duration = int((event.end_time - event.start_time).total_seconds() / 60)

        for slot_start, slot_end in available_slots:
            slot_duration = int((slot_end - slot_start).total_seconds() / 60)
            if slot_duration >= event_duration:
                # 找到合适的槽
                return AdjustmentSuggestion(
                    original_event=event,
                    new_start_time=slot_start,
                    new_end_time=slot_start + timedelta(minutes=event_duration),
                    reason=f"检测到冲突，建议调整到 {slot_start.strftime('%H:%M')}",
                    confidence=0.8,
                )

        return None

    def _find_available_slots(
        self, events: List[Event], target_date: date, buffer_minutes: int
    ) -> List[tuple]:
        """查找可用时间槽"""
        prefs = self.prefs.get_all()
        work_start = prefs.get("work_start_time", "09:00")
        work_end = prefs.get("work_end_time", "18:00")

        # 解析时间
        start_h, start_m = map(int, work_start.split(":"))
        end_h, end_m = map(int, work_end.split(":"))

        day_start = datetime.combine(target_date, time(start_h, start_m))
        day_end = datetime.combine(target_date, time(end_h, end_m))

        # 按开始时间排序
        sorted_events = sorted(events, key=lambda e: e.start_time)

        slots = []
        current_time = day_start

        for event in sorted_events:
            # 只考虑当天的事件
            if event.start_time.date() != target_date:
                continue

            event_start = event.start_time - timedelta(minutes=buffer_minutes)
            event_end = event.end_time + timedelta(minutes=buffer_minutes)

            if current_time < event_start:
                slots.append((current_time, event_start))

            current_time = max(current_time, event_end)

        if current_time < day_end:
            slots.append((current_time, day_end))

        return slots

    def auto_adjust_after_completion(self, completed_event: Event) -> List[Dict]:
        """事件完成后自动调整后续日程"""
        # 计算实际用时
        actual_duration = int(
            (datetime.now() - completed_event.start_time).total_seconds() / 60
        )
        planned_duration = int(
            (completed_event.end_time - completed_event.start_time).total_seconds() / 60
        )

        delta = actual_duration - planned_duration

        if abs(delta) < 10:
            return []  # 差异不大，不需要调整

        # 获取后续事件
        from sqlalchemy import func
        target_date = completed_event.start_time.date()
        following_events = (
            self.db.query(Event)
            .filter(func.date(Event.start_time) == target_date)
            .filter(Event.start_time > completed_event.end_time)
            .filter(Event.status == Status.pending)
            .order_by(Event.start_time)
            .all()
        )

        adjustments = []
        for event in following_events:
            new_start = event.start_time + timedelta(minutes=delta)
            new_end = event.end_time + timedelta(minutes=delta)

            event.start_time = new_start
            event.end_time = new_end

            adjustments.append({
                "event_id": event.id,
                "event_title": event.title,
                "old_start": event.start_time.isoformat(),
                "new_start": new_start.isoformat(),
                "delta_minutes": delta,
            })

        if adjustments:
            self.db.commit()

        return adjustments

    def smart_reorder(self, target_date: date = None) -> List[Dict]:
        """智能重新排序日程"""
        if target_date is None:
            target_date = date.today()

        from sqlalchemy import func
        events = (
            self.db.query(Event)
            .filter(func.date(Event.start_time) == target_date)
            .filter(Event.status == Status.pending)
            .all()
        )

        if len(events) < 2:
            return []

        prefs = self.prefs.get_all()
        deep_work_first = prefs.get("deep_work_first", "true") == "true"

        # 智能排序
        def sort_key(event):
            # 优先级分数
            priority_score = {
                Priority.urgent: 100,
                Priority.high: 75,
                Priority.medium: 50,
                Priority.low: 25,
            }.get(event.priority, 50)

            # 深度工作优先
            deep_work_bonus = 0
            if deep_work_first and "工作" in event.title or "重要" in event.title:
                deep_work_bonus = 30

            return -(priority_score + deep_work_bonus)

        sorted_events = sorted(events, key=sort_key)

        # 重新分配时间
        prefs = self.prefs.get_all()
        work_start = prefs.get("work_start_time", "09:00")
        h, m = map(int, work_start.split(":"))
        current_time = datetime.combine(target_date, time(h, m))

        changes = []
        for event in sorted_events:
            duration = int((event.end_time - event.start_time).total_seconds() / 60)
            old_start = event.start_time

            event.start_time = current_time
            event.end_time = current_time + timedelta(minutes=duration)

            if old_start != current_time:
                changes.append({
                    "event_id": event.id,
                    "event_title": event.title,
                    "old_start": old_start.isoformat(),
                    "new_start": current_time.isoformat(),
                })

            current_time = event.end_time + timedelta(minutes=15)  # 缓冲

        if changes:
            self.db.commit()

        return changes
