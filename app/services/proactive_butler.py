import json
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import asdict

import httpx

from app.database import SessionLocal
from app.models import Event, Priority, Status
from app.services.conversation_state import (
    get_conversation,
    reset_conversation,
    CollectedInfo,
)
from app.services.preferences_service import PreferencesService
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


PLANNING_PROMPT = """你是"小管"，少爷的私人AI管家。

基于以下信息，为少爷规划充实的一天。

## 收集到的信息：
{collected_info}

## 少爷的日常习惯：
- 起床时间：{wake_up_time}
- 早餐时间：{breakfast_time}
- 工作开始：{work_start_time}
- 午餐时间：{lunch_time}
- 工作结束：{work_end_time}
- 晚餐时间：{dinner_time}
- 睡觉时间：{bed_time}

## 规划要求：
1. 从起床到睡觉，安排完整的一天
2. 包含：起床、洗漱、早餐、通勤、工作/学习、午餐、午休、下午茶、运动、放松、睡前准备等
3. 优先安排收集到的任务和活动
4. 紧急事项优先处理
5. 工作期间每小时安排5-10分钟休息
6. 午休30-60分钟
7. 运动时间：{exercise_time}
8. 根据少爷心情调整节奏（心情好可以多安排，累了就多安排放松）

返回JSON格式：
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
"""


class ProactiveButler:
    """主动管家服务"""

    def __init__(self):
        self.db = SessionLocal()
        self.prefs = PreferencesService()

    def close(self):
        self.db.close()
        self.prefs.close()

    def start_conversation(self, session_id: str = "default") -> str:
        """开始主动对话"""
        reset_conversation(session_id)
        conv = get_conversation(session_id)
        first_question = conv.start()
        return first_question

    def answer(self, user_message: str, session_id: str = "default") -> Dict[str, Any]:
        """处理用户回答，返回下一步"""
        conv = get_conversation(session_id)

        if not conv.is_active and not conv.is_finished:
            # 还没开始，开始对话
            question = self.start_conversation(session_id)
            return {
                "reply": question,
                "is_finished": False,
                "can_plan": False,
            }

        if conv.is_finished:
            # 已经完成了，直接规划
            plan = self._generate_plan_from_info(conv.info)
            return {
                "reply": f"好的！这就为您规划今天的行程：\n\n{plan.get('summary', '')}",
                "is_finished": True,
                "can_plan": True,
                "plan": plan,
            }

        # 处理回答
        next_question = conv.answer(user_message)

        if next_question:
            return {
                "reply": next_question,
                "is_finished": False,
                "can_plan": False,
            }
        else:
            # 对话完成，生成规划
            plan = self._generate_plan_from_info(conv.info)
            return {
                "reply": f"好的！了解了，这就为您规划今天的行程：\n\n{plan.get('summary', '')}",
                "is_finished": True,
                "can_plan": True,
                "plan": plan,
            }

    def _generate_plan_from_info(self, info: CollectedInfo) -> Dict[str, Any]:
        """基于收集到的信息生成规划"""
        # 获取偏好设置
        prefs = self.prefs.get_all()

        prompt = PLANNING_PROMPT.format(
            collected_info=self._format_collected_info(info),
            wake_up_time=prefs["wake_up_time"],
            breakfast_time=prefs["breakfast_time"],
            work_start_time=prefs["work_start_time"],
            lunch_time=prefs["lunch_time"],
            work_end_time=prefs["work_end_time"],
            dinner_time=prefs["dinner_time"],
            bed_time=prefs["bed_time"],
            exercise_time=info.exercise_time or prefs.get("exercise_time", "evening"),
        )

        if not LLM_API_KEY:
            return self._local_plan(info, prefs)

        try:
            import httpx
            resp = httpx.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是专业的私人管家，擅长时间管理和日程规划。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.4,
                },
                timeout=60.0,
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            content = self._extract_json(content)
            return json.loads(content.strip())
        except Exception as e:
            print(f"[主动管家] LLM调用失败: {e}")
            return self._local_plan(info, prefs)

    def _format_collected_info(self, info: CollectedInfo) -> str:
        """格式化收集到的信息"""
        lines = []
        if info.mood:
            lines.append(f"- 心情：{info.mood}")
        if info.main_goal:
            lines.append(f"- 主要目标：{info.main_goal}")
        if info.work_tasks:
            lines.append(f"- 工作任务：{', '.join(info.work_tasks)}")
        if info.meetings:
            lines.append(f"- 会议/约会：{len(info.meetings)}个")
        if info.exercise:
            lines.append(f"- 运动：{info.exercise}")
        if info.urgent_tasks:
            lines.append(f"- 紧急事项：{', '.join(info.urgent_tasks)}")
        if info.relax_activities:
            lines.append(f"- 放松活动：{', '.join(info.relax_activities)}")
        return "\n".join(lines) if lines else "（无特别信息）"

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

    def _local_plan(self, info: CollectedInfo, prefs: dict) -> Dict[str, Any]:
        """本地生成规划"""
        from datetime import datetime, time

        # 基础日程
        wake_time = prefs.get("wake_up_time", "07:00")
        breakfast_time = prefs.get("breakfast_time", "07:30")
        work_start = prefs.get("work_start_time", "09:00")
        lunch_time = prefs.get("lunch_time", "12:00")
        work_end = prefs.get("work_end_time", "18:00")
        dinner_time = prefs.get("dinner_time", "18:30")
        bed_time = prefs.get("bed_time", "23:00")

        schedule = []

        # 起床 & 洗漱
        schedule.append({
            "start_time": wake_time,
            "end_time": self._add_minutes(wake_time, 10),
            "title": "起床",
            "description": "起床、拉伸、喝一杯温水",
            "priority": "low",
            "category": "routine",
        })
        schedule.append({
            "start_time": self._add_minutes(wake_time, 10),
            "end_time": breakfast_time,
            "title": "晨间洗漱",
            "description": "洗脸、刷牙、护肤",
            "priority": "low",
            "category": "routine",
        })

        # 早餐
        schedule.append({
            "start_time": breakfast_time,
            "end_time": self._add_minutes(breakfast_time, 30),
            "title": "早餐",
            "description": "营养早餐时间",
            "priority": "medium",
            "category": "meal",
        })

        # 通勤/准备
        schedule.append({
            "start_time": self._add_minutes(breakfast_time, 30),
            "end_time": work_start,
            "title": "通勤/准备",
            "description": "前往工作地点或居家办公准备",
            "priority": "medium",
            "category": "routine",
        })

        # 上午工作
        current_time = work_start
        if info.work_tasks:
            for i, task in enumerate(info.work_tasks[:3]):
                is_urgent = any(u in task for u in info.urgent_tasks)
                schedule.append({
                    "start_time": current_time,
                    "end_time": self._add_minutes(current_time, 50),
                    "title": task,
                    "description": "",
                    "priority": "urgent" if is_urgent else "high",
                    "category": "work",
                })
                current_time = self._add_minutes(current_time, 50)
                schedule.append({
                    "start_time": current_time,
                    "end_time": self._add_minutes(current_time, 10),
                    "title": "休息",
                    "description": "起身活动、喝水",
                    "priority": "low",
                    "category": "rest",
                })
                current_time = self._add_minutes(current_time, 10)
                if current_time >= lunch_time:
                    break
        else:
            # 默认工作块
            while current_time < lunch_time:
                schedule.append({
                    "start_time": current_time,
                    "end_time": self._add_minutes(current_time, 50),
                    "title": "工作/学习",
                    "description": "专注工作时间",
                    "priority": "medium",
                    "category": "work",
                })
                current_time = self._add_minutes(current_time, 50)
                if current_time < lunch_time:
                    schedule.append({
                        "start_time": current_time,
                        "end_time": self._add_minutes(current_time, 10),
                        "title": "休息",
                        "description": "起身活动一下",
                        "priority": "low",
                        "category": "rest",
                    })
                    current_time = self._add_minutes(current_time, 10)

        # 午餐 & 午休
        schedule.append({
            "start_time": lunch_time,
            "end_time": self._add_minutes(lunch_time, 60),
            "title": "午餐",
            "description": "享用午餐",
            "priority": "medium",
            "category": "meal",
        })
        schedule.append({
            "start_time": self._add_minutes(lunch_time, 60),
            "end_time": self._add_minutes(lunch_time, 90),
            "title": "午休",
            "description": "小憩或冥想",
            "priority": "medium",
            "category": "rest",
        })

        # 下午工作
        current_time = self._add_minutes(lunch_time, 90)
        work_end_time = work_end
        remaining_tasks = info.work_tasks[3:] if info.work_tasks else []
        if remaining_tasks:
            for task in remaining_tasks:
                if current_time >= work_end_time:
                    break
                schedule.append({
                    "start_time": current_time,
                    "end_time": self._add_minutes(current_time, 50),
                    "title": task,
                    "description": "",
                    "priority": "high",
                    "category": "work",
                })
                current_time = self._add_minutes(current_time, 50)
                if current_time < work_end_time:
                    schedule.append({
                        "start_time": current_time,
                        "end_time": self._add_minutes(current_time, 10),
                        "title": "下午茶休息",
                        "description": "喝点东西、放松一下",
                        "priority": "low",
                        "category": "rest",
                    })
                    current_time = self._add_minutes(current_time, 10)
        else:
            while current_time < work_end_time:
                schedule.append({
                    "start_time": current_time,
                    "end_time": self._add_minutes(current_time, 50),
                    "title": "工作/学习",
                    "description": "继续处理任务",
                    "priority": "medium",
                    "category": "work",
                })
                current_time = self._add_minutes(current_time, 50)
                if current_time < work_end_time:
                    schedule.append({
                        "start_time": current_time,
                        "end_time": self._add_minutes(current_time, 10),
                        "title": "休息",
                        "description": "活动一下",
                        "priority": "low",
                        "category": "rest",
                    })
                    current_time = self._add_minutes(current_time, 10)

        # 运动
        if info.exercise:
            exercise_start = info.exercise_time or prefs.get("exercise_time", "evening")
            if exercise_start == "morning":
                exercise_time_slot = self._add_minutes(breakfast_time, 30)
            else:
                exercise_time_slot = work_end_time
            schedule.append({
                "start_time": exercise_time_slot,
                "end_time": self._add_minutes(exercise_time_slot, 45),
                "title": info.exercise,
                "description": "锻炼身体时间",
                "priority": "high",
                "category": "exercise",
            })
            current_time = self._add_minutes(exercise_time_slot, 45)
        else:
            current_time = work_end_time

        # 放松 & 晚餐
        schedule.append({
            "start_time": current_time,
            "end_time": dinner_time,
            "title": "放松",
            "description": "洗澡、换衣服、休息一下",
            "priority": "low",
            "category": "rest",
        })
        schedule.append({
            "start_time": dinner_time,
            "end_time": self._add_minutes(dinner_time, 60),
            "title": "晚餐",
            "description": "享用晚餐",
            "priority": "medium",
            "category": "meal",
        })

        # 晚间放松活动
        current_time = self._add_minutes(dinner_time, 60)
        if info.relax_activities:
            for activity in info.relax_activities:
                schedule.append({
                    "start_time": current_time,
                    "end_time": self._add_minutes(current_time, 45),
                    "title": activity,
                    "description": "放松时间",
                    "priority": "low",
                    "category": "leisure",
                })
                current_time = self._add_minutes(current_time, 45)
        else:
            schedule.append({
                "start_time": current_time,
                "end_time": self._add_minutes(current_time, 90),
                "title": "自由时间",
                "description": "阅读、学习或娱乐",
                "priority": "low",
                "category": "leisure",
            })
            current_time = self._add_minutes(current_time, 90)

        # 睡前准备
        schedule.append({
            "start_time": self._add_minutes(bed_time, -60),
            "end_time": bed_time,
            "title": "睡前准备",
            "description": "洗漱、放松、准备睡觉",
            "priority": "low",
            "category": "routine",
        })

        # 添加主要目标
        if info.main_goal:
            schedule.append({
                "start_time": work_start,
                "end_time": self._add_minutes(work_start, 60),
                "title": f"【重点】{info.main_goal}",
                "description": "今天的主要目标",
                "priority": "urgent",
                "category": "work",
            })

        # 添加紧急事项
        for urgent in info.urgent_tasks:
            if urgent != info.main_goal:
                schedule.append({
                    "start_time": self._add_minutes(work_start, 60),
                    "end_time": self._add_minutes(work_start, 90),
                    "title": f"【紧急】{urgent}",
                    "description": "需要优先处理",
                    "priority": "urgent",
                    "category": "work",
                })

        # 按时间排序
        schedule.sort(key=lambda x: x["start_time"])

        return {
            "summary": f"为您规划了充实的一天，包含{len(schedule)}个时段的安排。",
            "schedule": schedule,
        }

    def _add_minutes(self, time_str: str, minutes: int) -> str:
        """时间加分钟"""
        try:
            h, m = map(int, time_str.split(":"))
            total = h * 60 + m + minutes
            new_h = total // 60 % 24
            new_m = total % 60
            return f"{new_h:02d}:{new_m:02d}"
        except Exception:
            return time_str

    def apply_plan(self, plan: Dict[str, Any], target_date: datetime = None):
        """应用规划到事件表"""
        from app.models import Event, Priority, Status
        from datetime import date, time

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
                print(f"[主动管家] 跳过无效时段: {item}, 错误: {e}")

        self.db.commit()
        return created_events

    def get_conversation_summary(self, session_id: str = "default") -> Dict[str, Any]:
        """获取对话摘要"""
        conv = get_conversation(session_id)
        return conv.get_summary()

    def reset(self, session_id: str = "default"):
        """重置对话"""
        reset_conversation(session_id)
