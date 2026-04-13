import json
from datetime import datetime, time, timedelta, date
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

import httpx

from app.database import SessionLocal
from app.models import Event, Priority, Status, DayPlan
from app.services.preferences_service import PreferencesService
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


EXPERT_PLAN_PROMPT = """你是"小管"，少爷的私人管家兼时间管理专家。

你的风格：专业、高效、不啰嗦，像一个经验丰富的老管家。

## 少爷的日常习惯：
- 起床时间：{wake_up_time}
- 早餐时间：{breakfast_time}
- 工作开始：{work_start_time}
- 午餐时间：{lunch_time}
- 工作结束：{work_end_time}
- 晚餐时间：{dinner_time}
- 睡觉时间：{bed_time}
- 运动安排：{include_exercise}
- 运动时间偏好：{exercise_time}
- 事件缓冲：{buffer_minutes}分钟

## 任务：为少爷规划{target_date}的日程。

## 已有待办事件：
{existing_events}

## 要求：
1. 基于少爷的习惯直接规划，不要问基础问题。
2. 如果有不确定的地方（比如具体做什么运动、工作内容），可以问1-2个关键问题，但不要超过3个。
3. 安排要合理：
   - 深度工作优先在上午
   - 每小时休息10分钟
   - 午休30-60分钟
   - 预留灵活时间处理突发事
4. 返回格式：
{return_format}
"""


QUESTIONS_PROMPT = """直接返回JSON：
{{
  "confident": true/false,
  "questions": ["需要问少爷确认的问题列表，最多3个，没有就空数组],
  "draft_plan": {{
    "summary": "暂定的规划概要",
    "schedule": [...]
  }}
}}"""


PLAN_ONLY_PROMPT = """直接返回JSON：
{{
  "summary": "今天的整体规划概要",
  "schedule": [
    {{
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "title": "活动标题",
      "description": "详细说明",
      "priority": "urgent|high|medium|low",
      "category": "routine|work|meal|exercise|rest|leisure"
    }}
  ]
}}"""


SUMMARY_PROMPT = """你是"小管"，少爷的私人管家。

总结少爷今天的完成情况，并规划明天。

## 今天的日期：{today_date}

## 今天的事件：
{today_events}

## 明天的日期：{tomorrow_date}

## 少爷的日常习惯：
- 起床时间：{wake_up_time}
- 早餐时间：{breakfast_time}
- 工作开始：{work_start_time}
- 午餐时间：{lunch_time}
- 工作结束：{work_end_time}
- 晚餐时间：{dinner_time}
- 睡觉时间：{bed_time}

## 任务：
1. 简洁总结今天（3句话）
2. 规划明天的日程
3. 返回格式：
{{
  "summary": "今天的总结",
  "tomorrow_plan": {{
    "summary": "明天的规划概要",
    "schedule": [...]
  }}
}}
"""


@dataclass
class ButlerState:
    """管家状态"""
    current_plan_stage: str = "idle"  # idle, asking_questions, planning
    questions_asked: List[str] = None
    answers_received: Dict[str, str] = None
    draft_plan: Dict = None
    last_update: datetime = None

    def __post_init__(self):
        if self.questions_asked is None:
            self.questions_asked = []
        if self.answers_received is None:
            self.answers_received = {}
        if self.last_update is None:
            self.last_update = datetime.now()


class SmartButler:
    """智能管家"""

    def __init__(self):
        self.db = SessionLocal()
        self.prefs = PreferencesService()
        self.state = ButlerState()

    def close(self):
        self.db.close()
        self.prefs.close()

    def _get_events_for_date(self, target_date: date) -> List[Event]:
        """获取指定日期的事件"""
        from sqlalchemy import func
        return (
            self.db.query(Event)
            .filter(func.date(Event.start_time) == target_date)
            .order_by(Event.start_time)
            .all()
        )

    def _format_events(self, events: List[Event]) -> str:
        """格式化事件列表"""
        if not events:
            return "（无待办事件）"
        lines = []
        for e in events:
            status_mark = "✅" if e.status == Status.completed else ""
            lines.append(
                f"- {e.start_time.strftime('%H:%M')} {e.title} {status_mark}"
            )
            if e.description:
                lines.append(f"  说明: {e.description}")
        return "\n".join(lines)

    async def start_planning_conversation(self, user_message: str = None, target_date: date = None) -> Dict[str, Any]:
        """开始规划对话"""
        if target_date is None:
            target_date = date.today()

        prefs = self.prefs.get_all()
        events = self._get_events_for_date(target_date)

        if self.state.current_plan_stage == "idle":
            # 第一次交互
            return await self._start_planning(target_date, prefs, events)
        elif self.state.current_plan_stage == "asking_questions":
            # 回答问题阶段
            return await self._handle_answer(user_message, target_date, prefs)
        else:
            # 已完成规划
            return {
                "reply": "今天的规划已经完成啦，少爷还有什么吩咐？",
                "plan": self.state.draft_plan,
                "can_apply": True,
            }

    async def _start_planning(self, target_date: date, prefs: dict, events: List[Event]) -> Dict[str, Any]:
        """开始规划"""
        date_str = target_date.strftime("%Y-%m-%d")
        weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][target_date.weekday()]
        date_display = f"{date_str} ({weekday})"

        # 检查是否已有规划
        existing_plan = self.db.query(DayPlan).filter(DayPlan.date == date_str).first()
        if existing_plan and existing_plan.detailed_plan:
            plan = json.loads(existing_plan.detailed_plan)
            return {
                "reply": f"少爷，{date_display}已经规划好了。\n\n{plan.get('summary', '')}",
                "plan": plan,
                "can_apply": True,
            }

        # 生成规划
        prompt = EXPERT_PLAN_PROMPT.format(
            target_date=date_display,
            wake_up_time=prefs["wake_up_time"],
            breakfast_time=prefs["breakfast_time"],
            work_start_time=prefs["work_start_time"],
            lunch_time=prefs["lunch_time"],
            work_end_time=prefs["work_end_time"],
            dinner_time=prefs["dinner_time"],
            bed_time=prefs["bed_time"],
            include_exercise="安排" if prefs.get("include_exercise") == "true" else "不安排",
            exercise_time=prefs.get("exercise_time", "evening"),
            buffer_minutes=prefs["buffer_minutes"],
            existing_events=self._format_events(events),
            return_format=QUESTIONS_PROMPT,
        )

        result = await self._call_llm(prompt, has_questions=True)

        if result.get("confident", True) and not result.get("questions"):
            # 有疑问，需要问问题
            self.state.current_plan_stage = "asking_questions"
            self.state.questions_asked = result.get("questions", [])
            self.state.draft_plan = result.get("draft_plan")

            return {
                "reply": f"少爷，为您规划了一下，但有几个地方想确认一下：\n\n" +
                       "\n".join(f"{i+1}. {q}" for i, q in enumerate(self.state.questions_asked)),
                "plan": None,
                "can_apply": False,
            }
        else:
            # 直接生成最终规划
            final_plan = result.get("draft_plan") or result
            self.state.current_plan_stage = "planning"
            self.state.draft_plan = final_plan

            # 保存规划
            self._save_plan(date_str, final_plan)

            return {
                "reply": f"少爷，{date_display}已经为您规划好了。\n\n{final_plan.get('summary', '')}",
                "plan": final_plan,
                "can_apply": True,
            }

    async def _handle_answer(self, answer: str, target_date: date, prefs: dict) -> Dict[str, Any]:
        """处理用户回答"""
        # 保存回答
        question = self.state.questions_asked.pop(0)
        self.state.answers_received[question] = answer

        if self.state.questions_asked:
            # 还有问题要问
            return {
                "reply": f"好的，还有一个问题：\n\n{self.state.questions_asked[0]}",
                "plan": None,
                "can_apply": False,
            }
        else:
            # 没有问题了，生成最终规划
            date_str = target_date.strftime("%Y-%m-%d")

            # 使用已有草案+回答生成最终规划
            prompt = EXPERT_PLAN_PROMPT.format(
                target_date=date_str,
                wake_up_time=prefs["wake_up_time"],
                breakfast_time=prefs["breakfast_time"],
                work_start_time=prefs["work_start_time"],
                lunch_time=prefs["lunch_time"],
                work_end_time=prefs["work_end_time"],
                dinner_time=prefs["dinner_time"],
                bed_time=prefs["bed_time"],
                include_exercise="安排" if prefs.get("include_exercise") == "true" else "不安排",
                exercise_time=prefs.get("exercise_time", "evening"),
                buffer_minutes=prefs["buffer_minutes"],
                existing_events=self._format_events(self._get_events_for_date(target_date)),
                return_format=PLAN_ONLY_PROMPT,
            )

            # 添加用户回答
            prompt += "\n\n少爷补充说明：\n"
            for q, a in self.state.answers_received.items():
                prompt += f"- {q}: {a}\n"

            final_plan = await self._call_llm(prompt, has_questions=False)

            self.state.current_plan_stage = "planning"
            self.state.draft_plan = final_plan

            # 保存规划
            self._save_plan(date_str, final_plan)

            return {
                "reply": f"好的少爷，今天的规划已经完成。\n\n{final_plan.get('summary', '')}",
                "plan": final_plan,
                "can_apply": True,
            }

    async def _call_llm(self, prompt: str, has_questions: bool = False) -> Dict:
        """调用LLM"""
        if not LLM_API_KEY:
            return self._local_plan()

        try:
            resp = httpx.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是专业的私人管家兼时间管理专家，专业、高效、不啰嗦。只返回JSON，不要其他文字。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                },
                timeout=60.0,
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            content = self._extract_json(content)
            return json.loads(content.strip())
        except Exception as e:
            print(f"[智能管家] LLM调用失败: {e}")
            return self._local_plan()

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

    def _local_plan(self) -> Dict:
        """本地规划"""
        from app.services.ai_scheduler import AIScheduler
        scheduler = AIScheduler()
        # 复用本地规划逻辑
        info = type('obj', (object,), {
            'mood': 'normal',
            'main_goal': '',
            'work_tasks': [],
            'meetings': [],
            'exercise': '',
            'exercise_time': '',
            'urgent_tasks': [],
            'relax_activities': [],
        })()
        plan = scheduler._local_plan(info, self.prefs.get_all())
        scheduler.close()
        return plan

    def _save_plan(self, date_str: str, plan: Dict):
        """保存规划"""
        existing = self.db.query(DayPlan).filter(DayPlan.date == date_str).first()
        if existing:
            existing.ai_summary = plan.get("summary", "")
            existing.detailed_plan = json.dumps(plan, ensure_ascii=False)
            existing.is_auto_generated = True
        else:
            day_plan = DayPlan(
                date=date_str,
                ai_summary=plan.get("summary", ""),
                detailed_plan=json.dumps(plan, ensure_ascii=False),
                is_auto_generated=True,
            )
            self.db.add(day_plan)
        self.db.commit()

    def apply_plan(self, plan: Dict, target_date: date = None):
        """应用规划到事件表"""
        if target_date is None:
            target_date = date.today()

        schedule = plan.get("schedule", [])
        created_events = []

        for item in schedule:
            try:
                start_h, start_m = map(int, item["start_time"].split(":"))
                end_h, end_m = map(int, item["end_time"].split(":"))
                start = datetime.combine(target_date, time(start_h, start_m))
                end = datetime.combine(target_date, time(end_h, end_m))

                if end < datetime.now():
                    continue

                priority = Priority(item.get("priority", "medium"))
                event = Event(
                    title=item["title"],
                    description=item.get("description", ""),
                    start_time=start,
                    end_time=end,
                    priority=priority,
                    status=Status.pending,
                    is_ai_scheduled=True,
                )
                self.db.add(event)
                created_events.append(event)
            except Exception as e:
                print(f"[智能管家] 跳过无效时段: {item}, 错误: {e}")

        self.db.commit()
        return created_events

    async def daily_summary_and_plan(self):
        """每日总结和明日规划（晚上12点执行）"""
        today = date.today()
        tomorrow = today + timedelta(days=1)

        today_events = self._get_events_for_date(today)
        prefs = self.prefs.get_all()

        prompt = SUMMARY_PROMPT.format(
            today_date=today.strftime("%Y-%m-%d"),
            today_events=self._format_events(today_events),
            tomorrow_date=tomorrow.strftime("%Y-%m-%d"),
            wake_up_time=prefs["wake_up_time"],
            breakfast_time=prefs["breakfast_time"],
            work_start_time=prefs["work_start_time"],
            lunch_time=prefs["lunch_time"],
            work_end_time=prefs["work_end_time"],
            dinner_time=prefs["dinner_time"],
            bed_time=prefs["bed_time"],
        )

        result = await self._call_llm(prompt, has_questions=False)

        # 保存明天的规划
        if "tomorrow_plan" in result:
            self._save_plan(tomorrow.isoformat(), result["tomorrow_plan"])

        return result

    def reset(self):
        """重置状态"""
        self.state = ButlerState()


# 全局状态
_butler_instances: Dict[str, SmartButler] = {}


def get_smart_butler(session_id: str = "default") -> SmartButler:
    if session_id not in _butler_instances:
        _butler_instances[session_id] = SmartButler()
    return _butler_instances[session_id]
