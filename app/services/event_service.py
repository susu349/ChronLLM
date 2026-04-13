from datetime import datetime, date, timedelta

from sqlalchemy import func

from app.database import SessionLocal
from app.models import Event, Reminder, Priority, Status
from config import DEFAULT_REMINDER_MINUTES


class EventService:
    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def create_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: str = "",
        priority: Priority = Priority.medium,
        location: str = "",
        participants: str = "",
        task_steps: str = "",
        notes: str = "",
        category: str = "",
    ) -> Event:
        import json
        event = Event(
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            priority=priority,
            location=location,
            notes=notes,
            category=category,
        )
        # 处理 participants (JSON 数组)
        if participants:
            if isinstance(participants, str):
                if participants.strip().startswith('['):
                    event.participants = participants
                else:
                    parts = [p.strip() for p in participants.split(',') if p.strip()]
                    event.participants = json.dumps(parts, ensure_ascii=False)
            else:
                event.participants = json.dumps(participants, ensure_ascii=False)
        # 处理 task_steps (JSON 数组)
        if task_steps:
            if isinstance(task_steps, str):
                if task_steps.strip().startswith('['):
                    event.task_steps = task_steps
                else:
                    parts = [s.strip() for s in task_steps.split('\n') if s.strip()]
                    event.task_steps = json.dumps(parts, ensure_ascii=False)
            else:
                event.task_steps = json.dumps(task_steps, ensure_ascii=False)
        self.db.add(event)
        self.db.add(Reminder(
            event_id=event.id,
            trigger_time=start_time - timedelta(minutes=DEFAULT_REMINDER_MINUTES),
        ))
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_today_events(self) -> list[Event]:
        today = date.today()
        return (
            self.db.query(Event)
            .filter(func.date(Event.start_time) == today)
            .order_by(Event.start_time)
            .all()
        )

    def get_all_events(self) -> list[Event]:
        return self.db.query(Event).order_by(Event.start_time).all()

    def get_event(self, event_id: int) -> Event | None:
        return self.db.query(Event).filter(Event.id == event_id).first()

    def update_event(self, event_id: int, **kwargs) -> Event | None:
        event = self.get_event(event_id)
        if not event:
            return None
        for key, value in kwargs.items():
            if hasattr(event, key):
                setattr(event, key, value)
        self.db.commit()
        self.db.refresh(event)
        return event

    def complete_event(self, event_id: int) -> bool:
        event = self.update_event(event_id, status=Status.completed)
        return event is not None

    def delete_event(self, event_id: int) -> bool:
        event = self.get_event(event_id)
        if not event:
            return False
        self.db.delete(event)
        self.db.commit()
        return True

    def get_pending_reminders(self) -> list[Reminder]:
        now = datetime.now()
        return (
            self.db.query(Reminder)
            .filter(Reminder.notified == False, Reminder.trigger_time <= now)
            .all()
        )
