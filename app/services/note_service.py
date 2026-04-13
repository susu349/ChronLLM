import json
from datetime import datetime, date
from typing import List, Dict, Any, Optional

from app.database import SessionLocal
from app.models import Note, EventSummary, DailySummary, DayPlan, Event, Status


class NoteService:
    """记事板服务"""

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    # ============ Note CRUD ============

    def create_note(
        self,
        date_str: str,
        title: str,
        content: str,
        note_type: str = "general",
        tags: List[str] = None,
        is_ai_generated: bool = False,
        day_plan_id: int = None,
    ) -> Note:
        """创建笔记"""
        note = Note(
            date=date_str,
            title=title,
            content=content,
            note_type=note_type,
            tags=",".join(tags) if tags else "",
            is_ai_generated=is_ai_generated,
            day_plan_id=day_plan_id,
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def get_notes_by_date(self, date_str: str, note_type: str = None) -> List[Note]:
        """获取指定日期的笔记"""
        query = self.db.query(Note).filter(Note.date == date_str)
        if note_type:
            query = query.filter(Note.note_type == note_type)
        return query.order_by(Note.created_at.desc()).all()

    def get_recent_notes(self, limit: int = 20) -> List[Note]:
        """获取最近的笔记"""
        return self.db.query(Note).order_by(Note.created_at.desc()).limit(limit).all()

    def search_notes(self, keyword: str) -> List[Note]:
        """搜索笔记"""
        return self.db.query(Note).filter(
            (Note.title.contains(keyword)) | (Note.content.contains(keyword))
        ).order_by(Note.created_at.desc()).all()

    def update_note(self, note_id: int, title: str = None, content: str = None, tags: List[str] = None) -> Optional[Note]:
        """更新笔记"""
        note = self.db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return None
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
        if tags is not None:
            note.tags = ",".join(tags)
        note.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(note)
        return note

    def delete_note(self, note_id: int) -> bool:
        """删除笔记"""
        note = self.db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return False
        self.db.delete(note)
        self.db.commit()
        return True

    # ============ Event Summary ============

    def create_event_summary(
        self,
        event_id: int,
        completion_rate: int,
        summary: str = "",
        reflection: str = "",
        obstacles: str = "",
    ) -> EventSummary:
        """创建事件总结"""
        event_summary = EventSummary(
            event_id=event_id,
            completion_rate=completion_rate,
            summary=summary,
            reflection=reflection,
            obstacles=obstacles,
        )
        self.db.add(event_summary)
        self.db.commit()
        self.db.refresh(event_summary)
        return event_summary

    def get_event_summary(self, event_id: int) -> Optional[EventSummary]:
        """获取事件总结"""
        return self.db.query(EventSummary).filter(EventSummary.event_id == event_id).first()

    # ============ Daily Summary ============

    def create_daily_summary(
        self,
        date_str: str,
        overall_summary: str,
        completion_rate: int,
        highlights: List[Dict] = None,
        improvements: List[Dict] = None,
        tomorrow_plan: Dict = None,
    ) -> DailySummary:
        """创建每日总结"""
        daily_summary = DailySummary(
            date=date_str,
            overall_summary=overall_summary,
            completion_rate=completion_rate,
            highlights=json.dumps(highlights, ensure_ascii=False) if highlights else "[]",
            improvements=json.dumps(improvements, ensure_ascii=False) if improvements else "[]",
            tomorrow_plan=json.dumps(tomorrow_plan, ensure_ascii=False) if tomorrow_plan else "{}",
        )
        self.db.add(daily_summary)
        self.db.commit()
        self.db.refresh(daily_summary)

        # 同时创建笔记
        self.create_note(
            date_str=date_str,
            title=f"{date_str} 每日总结",
            content=overall_summary,
            note_type="summary",
            tags=["每日总结", "AI生成"],
            is_ai_generated=True,
        )

        return daily_summary

    def get_daily_summary(self, date_str: str) -> Optional[DailySummary]:
        """获取每日总结"""
        return self.db.query(DailySummary).filter(DailySummary.date == date_str).first()

    def calculate_daily_completion_rate(self, date_str: str) -> int:
        """计算某日的完成率"""
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            return 0

        from sqlalchemy import func

        events = self.db.query(Event).filter(
            func.date(Event.start_time) == target_date
        ).all()

        if not events:
            return 0

        completed = sum(1 for e in events if e.status == Status.completed)
        return int(completed / len(events) * 100)

    # ============ Planning Notes ============

    def create_planning_note(
        self,
        date_str: str,
        plan_content: Dict,
        thinking_process: str = "",
    ) -> Note:
        """创建规划过程笔记"""
        content = json.dumps(plan_content, ensure_ascii=False, indent=2)
        if thinking_process:
            content = f"## 思考过程\n\n{thinking_process}\n\n## 规划内容\n\n```json\n{content}\n```"

        return self.create_note(
            date_str=date_str,
            title=f"{date_str} 规划过程",
            content=content,
            note_type="plan",
            tags=["规划", "AI生成"],
            is_ai_generated=True,
        )

    def to_dict(self, obj) -> Dict[str, Any]:
        """转换对象为字典"""
        if isinstance(obj, Note):
            return {
                "id": obj.id,
                "date": obj.date,
                "title": obj.title,
                "content": obj.content,
                "note_type": obj.note_type,
                "tags": obj.tags.split(",") if obj.tags else [],
                "is_ai_generated": obj.is_ai_generated,
                "created_at": obj.created_at.isoformat() if obj.created_at else None,
                "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
            }
        elif isinstance(obj, EventSummary):
            return {
                "id": obj.id,
                "event_id": obj.event_id,
                "completion_rate": obj.completion_rate,
                "summary": obj.summary,
                "reflection": obj.reflection,
                "obstacles": obj.obstacles,
                "created_at": obj.created_at.isoformat() if obj.created_at else None,
            }
        elif isinstance(obj, DailySummary):
            return {
                "id": obj.id,
                "date": obj.date,
                "overall_summary": obj.overall_summary,
                "completion_rate": obj.completion_rate,
                "highlights": json.loads(obj.highlights) if obj.highlights else [],
                "improvements": json.loads(obj.improvements) if obj.improvements else [],
                "tomorrow_plan": json.loads(obj.tomorrow_plan) if obj.tomorrow_plan else {},
                "created_at": obj.created_at.isoformat() if obj.created_at else None,
            }
        return {}
