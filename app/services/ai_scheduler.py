import json
from datetime import datetime, timedelta, time
from typing import List, Dict, Optional, Tuple

import httpx

from app.models import Event, DayPlan, Priority, Status
from app.database import SessionLocal
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from app.services.preferences_service import PreferencesService
from app.services.plan_reviewer import PlanReviewer


DETAILED_PLAN_PROMPT = """你是"小管"，少爷的私人AI管家。你的任务是为少爷精心规划一整天的详细行程。

当前信息：
- 日期：{date_str} ({weekday_cn})
- 已有待办事件：
{existing_events}

少爷的日常习惯：
- 起床时间：{wake_up_time}
- 早餐时间：{breakfast_time}
- 工作开始：{work_start_time}
- 午餐时间：{lunch_time}
- 工作结束：{work_end_time}
- 晚餐时间：{dinner_time}
- 睡觉时间：{bed_time}
- 事件缓冲：{buffer_minutes}分钟
- 安排运动：{include_exercise}
- 运动时长：{exercise_duration}分钟
- 运动时间：{exercise_time}
- 深度工作优先：{deep_work_first}

规划要求：
1. 从起床到睡觉，安排完整的一天
2. 包含：起床、洗漱、早餐、通勤、工作/学习、午餐、午休、下午茶、晚餐、运动、阅读、放松等
3. 每个时间段都要有明确的活动安排
4. 已有事件必须保留并合理安排
5. 优先安排紧急和高优先级事件
6. 工作期间穿插短休息（每小时5-10分钟）
7. 午休30-60分钟
8. 运动时间固定在{exercise_time}
9. 睡前1小时放松准备

请返回详细的JSON规划，格式如下：
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
}}

只返回JSON，不要其他文字。"""


class AIScheduler:
    def __init__(self):
        self.db = SessionLocal()
        self.prefs = PreferencesService()

    def close(self):
        self.db.close()
        self.prefs.close()

    def get_today_pending_events(self) -> List[Event]:
        """获取今日待办事件"""
        from sqlalchemy import func
        from datetime import date

        today = date.today()
        return (
            self.db.query(Event)
            .filter(
                func.date(Event.start_time) == today,
                Event.status != Status.completed,
            )
            .order_by(Event.start_time)
            .all()
        )

    def _build_events_list(self, events: List[Event]) -> str:
        """格式化事件列表"""
        if not events:
            return "  (无待办事件)"
        lines = []
        for e in events:
            lines.append(
                f"  - [{e.priority.value}] {e.title} "
                f"(原定: {e.start_time.strftime('%H:%M')}-{e.end_time.strftime('%H:%M')})"
            )
            if e.description:
                lines.append(f"    说明: {e.description}")
        return "\n".join(lines)

    def _get_weekday_cn(self, d: datetime) -> str:
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return days[d.weekday()]

    async def generate_detailed_plan(self, target_date: Optional[datetime] = None, with_review: bool = True, max_retry: int = 2) -> dict:
        """生成详细的一天规划（带审查机制）"""
        if target_date is None:
            target_date = datetime.now()

        date_str = target_date.strftime("%Y-%m-%d")
        weekday_cn = self._get_weekday_cn(target_date)
        events = self.get_today_pending_events()

        # 获取用户偏好
        prefs = self.prefs.get_all()

        prompt = DETAILED_PLAN_PROMPT.format(
            date_str=date_str,
            weekday_cn=weekday_cn,
            existing_events=self._build_events_list(events),
            wake_up_time=prefs["wake_up_time"],
            breakfast_time=prefs["breakfast_time"],
            work_start_time=prefs["work_start_time"],
            lunch_time=prefs["lunch_time"],
            work_end_time=prefs["work_end_time"],
            dinner_time=prefs["dinner_time"],
            bed_time=prefs["bed_time"],
            buffer_minutes=prefs["buffer_minutes"],
            include_exercise=prefs["include_exercise"],
            exercise_duration=prefs["exercise_duration"],
            exercise_time=prefs["exercise_time"],
            deep_work_first=prefs["deep_work_first"],
        )

        # 生成规划（可重试）
        result = None
        review_issues = []
        passed = False
        reviewer = PlanReviewer()

        for attempt in range(max_retry + 1):
            if not LLM_API_KEY:
                result = self._local_detailed_plan(target_date, events, prefs)
            else:
                try:
                    # 如果是重试，在prompt中添加审查反馈
                    current_prompt = prompt
                    if attempt > 0 and review_issues:
                        feedback = "\n\n【审查反馈 - 请修改以下问题】\n"
                        for issue in review_issues[:5]:  # 只显示前5个问题
                            feedback += f"- {issue['message']}\n"
                        current_prompt += feedback

                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            f"{LLM_BASE_URL}/chat/completions",
                            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                            json={
                                "model": LLM_MODEL,
                                "messages": [
                                    {"role": "system", "content": "你是专业的私人管家，擅长时间管理和日程规划。请仔细检查并避免深夜安排、时间冲突等问题。"},
                                    {"role": "user", "content": current_prompt},
                                ],
                                "temperature": 0.4,
                            },
                            timeout=httpx.Timeout(120.0, connect=10.0),
                        )
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        content = self._extract_json(content)
                        result = json.loads(content.strip())
                except Exception as e:
                    print(f"[AI规划] LLM调用失败: {e}，使用本地规划")
                    result = self._local_detailed_plan(target_date, events, prefs)

            # 审查规划
            if with_review and result:
                passed, issues = reviewer.review(result)
                review_issues = reviewer.issues_to_dict(issues)
                summary = reviewer.get_summary(issues)

                print(f"[AI规划] 第{attempt+1}次规划审查结果: "
                      f"{'通过' if passed else '未通过'}, "
                      f"{summary['errors']}个错误, {summary['warnings']}个警告")

                if passed:
                    break
                if attempt >= max_retry:
                    print(f"[AI规划] 已达最大重试次数，使用最后一次规划")
                    break
            else:
                passed = True
                break

        # 添加审查信息到结果
        if result:
            result["review"] = {
                "passed": passed,
                "issues": review_issues,
                "attempts": attempt + 1,
            }

        return result

    def _extract_json(self, text: str) -> str:
        """提取JSON内容"""
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

    def _local_detailed_plan(self, target_date: datetime, events: List[Event], prefs: dict) -> dict:
        """本地生成详细规划（无API时的备选）"""
        date_str = target_date.strftime("%Y-%m-%d")

        # 基础日程模板
        routine = [
            ("07:00", "07:10", "起床", "起床、拉伸、喝一杯温水", "low", "routine"),
            ("07:10", "07:30", "晨间洗漱", "洗脸、刷牙、护肤", "low", "routine"),
            ("07:30", "08:00", "早餐", "营养早餐时间", "medium", "meal"),
            ("08:00", "09:00", "通勤/准备", "前往工作地点或居家办公准备", "medium", "routine"),
            ("09:00", "10:00", "深度工作", "处理最重要的任务", "high", "work"),
            ("10:00", "10:10", "休息", "起身活动、喝水", "low", "rest"),
            ("10:10", "11:00", "工作", "继续处理任务", "high", "work"),
            ("11:00", "11:10", "休息", "眼保健操、拉伸", "low", "rest"),
            ("11:10", "12:00", "工作", "上午收尾工作", "medium", "work"),
            ("12:00", "13:00", "午餐", "享用午餐", "medium", "meal"),
            ("13:00", "13:30", "午休", "小憩或冥想", "medium", "rest"),
            ("13:30", "14:30", "工作", "下午工作开始", "medium", "work"),
            ("14:30", "14:40", "休息", "下午茶时间", "low", "rest"),
            ("14:40", "15:40", "工作", "继续工作", "medium", "work"),
            ("15:40", "15:50", "休息", "活动一下", "low", "rest"),
            ("15:50", "17:00", "工作", "下午工作收尾", "medium", "work"),
            ("17:00", "18:00", "运动", "锻炼身体", "high", "exercise"),
            ("18:00", "18:30", "放松", "洗澡、换衣服", "low", "rest"),
            ("18:30", "19:30", "晚餐", "享用晚餐", "medium", "meal"),
            ("19:30", "21:00", "自由时间", "阅读、学习或娱乐", "low", "leisure"),
            ("21:00", "22:00", "睡前准备", "洗漱、放松", "low", "routine"),
            ("22:00", "23:00", "睡眠", "进入梦乡", "low", "rest"),
        ]

        # 合并用户已有事件
        schedule = []
        for start, end, title, desc, priority, category in routine:
            schedule.append({
                "start_time": start,
                "end_time": end,
                "title": title,
                "description": desc,
                "priority": priority,
                "category": category,
            })

        # 添加用户的待办事件
        for e in events:
            schedule.append({
                "start_time": e.start_time.strftime("%H:%M"),
                "end_time": e.end_time.strftime("%H:%M"),
                "title": e.title,
                "description": e.description or "",
                "priority": e.priority.value,
                "category": "work",
            })

        # 按开始时间排序
        schedule.sort(key=lambda x: x["start_time"])

        return {
            "summary": f"为您规划了充实的一天，包含{len(schedule)}个时间段的安排。",
            "schedule": schedule,
        }

    def save_detailed_plan(self, date_str: str, plan: dict, is_auto: bool = False) -> DayPlan:
        """保存详细规划"""
        existing = self.db.query(DayPlan).filter(DayPlan.date == date_str).first()
        if existing:
            existing.ai_summary = plan.get("summary", "")
            existing.detailed_plan = json.dumps(plan, ensure_ascii=False)
            existing.is_auto_generated = is_auto
        else:
            day_plan = DayPlan(
                date=date_str,
                ai_summary=plan.get("summary", ""),
                detailed_plan=json.dumps(plan, ensure_ascii=False),
                is_auto_generated=is_auto,
            )
            self.db.add(day_plan)
        self.db.commit()
        return existing or day_plan

    def get_plan(self, date_str: str) -> Optional[DayPlan]:
        """获取指定日期的规划"""
        return self.db.query(DayPlan).filter(DayPlan.date == date_str).first()

    def apply_plan_to_events(self, date_str: str, plan: dict):
        """将规划应用到事件表"""
        from datetime import date, timedelta

        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            target_date = date.today()

        schedule = plan.get("schedule", [])
        created_events = []

        for item in schedule:
            try:
                start_h, start_m = map(int, item["start_time"].split(":"))
                end_h, end_m = map(int, item["end_time"].split(":"))
                start = datetime.combine(target_date, time(start_h, start_m))
                end = datetime.combine(target_date, time(end_h, end_m))

                # 跳过过去的事件
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
                print(f"[AI规划] 跳过无效时段: {item}, 错误: {e}")

        self.db.commit()
        return created_events

    async def generate_schedule(self):
        """旧版接口兼容 - 简单编排"""
        events = self.get_today_pending_events()
        if not events:
            return {"summary": "无待编排事件", "events": []}

        # 使用本地编排逻辑
        return self._simple_local_schedule(events)

    def _simple_local_schedule(self, events: List[Event]) -> dict:
        """简单的本地编排（兼容旧版）"""
        priority_order = {
            Priority.urgent: 0,
            Priority.high: 1,
            Priority.medium: 2,
            Priority.low: 3,
        }
        sorted_events = sorted(events, key=lambda e: priority_order.get(e.priority, 2))

        now = datetime.now()
        base_time = max(now.replace(second=0, microsecond=0), now.replace(hour=8, minute=0, second=0, microsecond=0))
        scheduled = []
        for e in sorted_events:
            duration = e.end_time - e.start_time
            scheduled.append(
                {
                    "event_id": e.id,
                    "suggested_start": base_time.isoformat(),
                    "reason": f"优先级: {e.priority.value}",
                }
            )
            base_time += duration + timedelta(minutes=15)

        return {
            "summary": "按优先级重新安排今日事件",
            "events": scheduled,
        }

    def save_day_plan(self, result: dict):
        """保存简单编排（兼容旧版）"""
        from datetime import date
        today_str = date.today().isoformat()
        plan = self.db.query(DayPlan).filter(DayPlan.date == today_str).first()
        if plan:
            plan.ai_summary = json.dumps(result, ensure_ascii=False)
        else:
            plan = DayPlan(date=today_str, ai_summary=json.dumps(result, ensure_ascii=False))
            self.db.add(plan)
        self.db.commit()
        return plan
