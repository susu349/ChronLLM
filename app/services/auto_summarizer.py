import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

import httpx

from app.database import SessionLocal
from app.models import Event, Priority, Status, EventSummary, DailySummary, Note
from app.services.preferences_service import PreferencesService
from app.services.note_service import NoteService
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


AUTO_SUMMARY_PROMPT = """你是"小管"，少爷的私人管家。

少爷不爱动脑子也不爱动手，所以你需要自动为他生成总结，不需要他手动填写。

## 事件信息：
- 标题：{event_title}
- 描述：{event_description}
- 计划时间：{start_time} 到 {end_time}
- 实际完成时间：{actual_end_time}
- 优先级：{priority}

## 请自动生成：
1. 完成度（0-100）：根据事件类型和完成情况评估
2. 总结：用简洁的话总结这个事件做了什么
3. 反思：有什么可以改进的地方，或者有什么收获
4. 遇到的困难（如果有）

返回JSON格式：
{{
  "completion_rate": 0-100,
  "summary": "总结内容",
  "reflection": "反思内容",
  "obstacles": "遇到的困难，没有则为空"
}}
"""


DAILY_SUMMARY_PROMPT = """你是"小管"，少爷的私人管家。

少爷不爱动脑子也不爱动手，请自动为他生成今日总结。

## 今日日期：{date}

## 今日事件：
{events_list}

## 请生成：
1. 整体总结：用3-5句话总结今天
2. 亮点：今天做得好的地方（JSON数组）
3. 改进建议：明天可以做得更好的地方（JSON数组）

返回JSON格式：
{{
  "overall_summary": "整体总结",
  "highlights": ["亮点1", "亮点2"],
  "improvements": ["建议1", "建议2"]
}}
"""


class AutoSummarizer:
    """自动总结生成器 - 不需要少爷动手动脑"""

    def __init__(self):
        self.db = SessionLocal()
        self.prefs = PreferencesService()

    def close(self):
        self.db.close()
        self.prefs.close()

    def auto_generate_event_summary(self, event: Event) -> EventSummary:
        """自动生成事件总结"""
        # 先尝试用LLM生成
        if LLM_API_KEY:
            try:
                summary = self._generate_with_llm(event)
                if summary:
                    return self._save_summary(event.id, summary)
            except Exception as e:
                print(f"[自动总结] LLM生成失败: {e}")

        # LLM不可用时用本地规则生成
        summary = self._generate_local(event)
        return self._save_summary(event.id, summary)

    def _generate_with_llm(self, event: Event) -> Optional[Dict]:
        """用LLM生成总结"""
        prompt = AUTO_SUMMARY_PROMPT.format(
            event_title=event.title,
            event_description=event.description or "无",
            start_time=event.start_time.strftime("%H:%M"),
            end_time=event.end_time.strftime("%H:%M"),
            actual_end_time=datetime.now().strftime("%H:%M"),
            priority=event.priority.value,
        )

        resp = httpx.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "你是专业的私人管家，擅长总结和反思。只返回JSON，不要其他文字。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
            },
            timeout=30.0,
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        content = self._extract_json(content)
        return json.loads(content.strip())

    def _generate_local(self, event: Event) -> Dict:
        """本地规则生成总结"""
        # 根据事件类型生成
        title_lower = event.title.lower()

        # 智能判断完成度
        if "会议" in event.title or "会" in event.title:
            completion_rate = 90
            summary = f"完成了「{event.title}」，会议顺利进行。"
            reflection = "下次可以提前准备更充分的材料。"
        elif "工作" in event.title or "任务" in event.title:
            completion_rate = 85
            summary = f"完成了工作任务「{event.title}」。"
            reflection = "效率不错，继续保持。"
        elif "学习" in event.title or "看书" in event.title or "阅读" in event.title:
            completion_rate = 80
            summary = f"完成了学习任务「{event.title}」，收获很大。"
            reflection = "明天可以继续这个进度。"
        elif "运动" in event.title or "健身" in event.title or "跑步" in event.title:
            completion_rate = 95
            summary = f"完成了运动「{event.title}」，感觉很好！"
            reflection = "坚持运动，保持健康！"
        elif "休息" in event.title or "放松" in event.title:
            completion_rate = 100
            summary = f"休息好了，精力恢复。"
            reflection = "适当的休息很重要。"
        else:
            completion_rate = 85
            summary = f"完成了「{event.title}」。"
            reflection = "继续保持！"

        # 高优先级事件完成度加5分
        if event.priority == Priority.urgent:
            completion_rate = min(100, completion_rate + 10)
            summary += "（紧急任务优先完成）"
        elif event.priority == Priority.high:
            completion_rate = min(100, completion_rate + 5)

        return {
            "completion_rate": completion_rate,
            "summary": summary,
            "reflection": reflection,
            "obstacles": "",
        }

    def _save_summary(self, event_id: int, data: Dict) -> EventSummary:
        """保存总结到数据库"""
        summary = EventSummary(
            event_id=event_id,
            completion_rate=data.get("completion_rate", 80),
            summary=data.get("summary", ""),
            reflection=data.get("reflection", ""),
            obstacles=data.get("obstacles", ""),
        )
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)

        # 同时创建笔记
        note_service = NoteService()
        note_service.create_note(
            date_str=summary.created_at.date().isoformat(),
            title=f"事件总结: {summary.event.title}",
            content=f"## 总结\n\n{summary.summary}\n\n## 反思\n\n{summary.reflection}",
            note_type="summary",
            tags=["自动总结", "AI生成"],
            is_ai_generated=True,
        )
        note_service.close()

        return summary

    def _extract_json(self, text: str) -> str:
        """提取JSON"""
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:]
                try:
                    json.loads(part)
                    return part
                except json.JSONDecodeError:
                    continue
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end+1]
        return text

    def auto_generate_daily_summary(self, target_date: date = None) -> DailySummary:
        """自动生成每日总结"""
        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        from sqlalchemy import func
        events = (
            self.db.query(Event)
            .filter(func.date(Event.start_time) == target_date)
            .all()
        )

        # 计算完成率
        total = len(events)
        completed = sum(1 for e in events if e.status == Status.completed)
        completion_rate = int(completed / total * 100) if total > 0 else 0

        # 生成总结
        if LLM_API_KEY:
            try:
                summary = self._generate_daily_with_llm(target_date, events)
                return self._save_daily_summary(target_date, summary, completion_rate)
            except Exception as e:
                print(f"[每日总结] LLM生成失败: {e}")

        # 本地生成
        summary = self._generate_daily_local(target_date, events, completion_rate)
        return self._save_daily_summary(target_date, summary, completion_rate)

    def _generate_daily_with_llm(self, target_date: date, events: List[Event]) -> Dict:
        """用LLM生成每日总结"""
        events_list = []
        for e in events:
            status_mark = "✅" if e.status == Status.completed else "⏳"
            events_list.append(f"- {e.start_time.strftime('%H:%M')} {status_mark} {e.title}")

        prompt = DAILY_SUMMARY_PROMPT.format(
            date=target_date.isoformat(),
            events_list="\n".join(events_list) if events_list else "无事件",
        )

        resp = httpx.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "你是专业的私人管家，擅长总结和提供建议。只返回JSON，不要其他文字。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
            },
            timeout=30.0,
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        content = self._extract_json(content)
        return json.loads(content.strip())

    def _generate_daily_local(self, target_date: date, events: List[Event], completion_rate: int) -> Dict:
        """本地生成每日总结"""
        total = len(events)
        completed = sum(1 for e in events if e.status == Status.completed)

        if completion_rate >= 80:
            overall_summary = f"今天完成了 {completed}/{total} 个任务，表现很棒！继续保持这个势头。"
            highlights = ["完成率很高", "效率不错"]
            improvements = ["明天可以继续保持"]
        elif completion_rate >= 50:
            overall_summary = f"今天完成了 {completed}/{total} 个任务，还不错，明天可以更高效一些。"
            highlights = ["完成了部分任务"]
            improvements = ["提高效率", "优先完成重要任务"]
        else:
            overall_summary = f"今天完成了 {completed}/{total} 个任务，明天需要更专注一些。"
            highlights = ["至少开始了"]
            improvements = ["减少干扰", "制定清晰计划"]

        return {
            "overall_summary": overall_summary,
            "highlights": highlights,
            "improvements": improvements,
        }

    def _save_daily_summary(self, target_date: date, data: Dict, completion_rate: int) -> DailySummary:
        """保存每日总结"""
        existing = self.db.query(DailySummary).filter(DailySummary.date == target_date.isoformat()).first()

        if existing:
            existing.overall_summary = data.get("overall_summary", "")
            existing.completion_rate = completion_rate
            existing.highlights = json.dumps(data.get("highlights", []), ensure_ascii=False)
            existing.improvements = json.dumps(data.get("improvements", []), ensure_ascii=False)
        else:
            daily_summary = DailySummary(
                date=target_date.isoformat(),
                overall_summary=data.get("overall_summary", ""),
                completion_rate=completion_rate,
                highlights=json.dumps(data.get("highlights", []), ensure_ascii=False),
                improvements=json.dumps(data.get("improvements", []), ensure_ascii=False),
            )
            self.db.add(daily_summary)

        self.db.commit()

        # 创建笔记
        note_service = NoteService()
        note_service.create_note(
            date_str=target_date.isoformat(),
            title=f"{target_date.isoformat()} 每日总结",
            content=data.get("overall_summary", ""),
            note_type="summary",
            tags=["每日总结", "AI生成"],
            is_ai_generated=True,
        )
        note_service.close()

        return existing or daily_summary

    def get_intelligent_suggestions(self) -> List[Dict]:
        """根据历史数据获取智能建议"""
        from sqlalchemy import func, extract

        # 获取最近7天的数据
        week_ago = date.today() - timedelta(days=7)
        events = (
            self.db.query(Event)
            .filter(Event.start_time >= week_ago)
            .all()
        )

        suggestions = []

        # 分析时间段效率
        morning_count = sum(1 for e in events if 8 <= e.start_time.hour < 12)
        afternoon_count = sum(1 for e in events if 14 <= e.start_time.hour < 18)
        evening_count = sum(1 for e in events if 19 <= e.start_time.hour < 23)

        if morning_count > afternoon_count and morning_count > evening_count:
            suggestions.append({
                "type": "time_optimization",
                "title": "早上效率最高",
                "content": "根据历史数据，您早上的完成率最高，建议把重要任务安排在上午。",
                "priority": "high",
            })
        elif afternoon_count > morning_count:
            suggestions.append({
                "type": "time_optimization",
                "title": "下午状态好",
                "content": "您下午的工作状态不错，可以把需要专注的任务安排在下午。",
                "priority": "medium",
            })

        # 检查运动频率
        exercise_events = [e for e in events if "运动" in e.title or "健身" in e.title]
        if len(exercise_events) < 2:
            suggestions.append({
                "type": "health",
                "title": "建议增加运动",
                "content": "最近运动较少，建议每周安排2-3次运动时间。",
                "priority": "medium",
            })

        # 检查休息时间
        work_events = [e for e in events if "工作" in e.title]
        if len(work_events) > 5:
            suggestions.append({
                "type": "rest",
                "title": "注意劳逸结合",
                "content": "工作任务较多，记得安排适当的休息时间。",
                "priority": "medium",
            })

        if not suggestions:
            suggestions.append({
                "type": "general",
                "title": "保持好状态",
                "content": "您的日程安排得不错，继续保持！",
                "priority": "low",
            })

        return suggestions
