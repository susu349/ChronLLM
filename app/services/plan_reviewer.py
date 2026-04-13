"""规划审查服务 - 检查AI生成的日程规划是否合理"""

import json
from datetime import datetime, time, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ReviewIssue:
    severity: IssueSeverity
    category: str
    message: str
    item_index: Optional[int] = None
    item_title: Optional[str] = None


class PlanReviewer:
    """规划审查器"""

    def __init__(self):
        # 默认合理时间范围
        self.reasonable_hours = {
            "wake": (6, 9),      # 合理起床时间 6:00-9:00
            "sleep": (21, 24),    # 合理睡觉时间 21:00-24:00
            "work": (8, 22),      # 合理工作时间 8:00-22:00
            "meal": {              # 合理用餐时间
                "breakfast": (6, 10),
                "lunch": (11, 14),
                "dinner": (17, 21),
            },
            "exercise": (6, 22),   # 合理运动时间
        }
        self.min_break_between = 5  # 事件间最小缓冲时间（分钟）
        self.max_event_duration = 4 * 60  # 单个事件最大时长（分钟）

    def parse_time(self, time_str: str) -> Optional[time]:
        """解析时间字符串"""
        try:
            h, m = map(int, time_str.split(":"))
            return time(h, m)
        except:
            return None

    def time_to_minutes(self, t: time) -> int:
        """时间转分钟数"""
        return t.hour * 60 + t.minute

    def get_duration_minutes(self, start: time, end: time) -> int:
        """计算时长（分钟）"""
        start_m = self.time_to_minutes(start)
        end_m = self.time_to_minutes(end)
        if end_m < start_m:
            end_m += 24 * 60  # 跨天
        return end_m - start_m

    def is_overlapping(self, s1: time, e1: time, s2: time, e2: time) -> bool:
        """检查两个时间段是否重叠"""
        s1_m = self.time_to_minutes(s1)
        e1_m = self.time_to_minutes(e1)
        s2_m = self.time_to_minutes(s2)
        e2_m = self.time_to_minutes(e2)

        # 处理跨天情况
        if e1_m < s1_m:
            e1_m += 24 * 60
        if e2_m < s2_m:
            e2_m += 24 * 60

        return not (e1_m <= s2_m or e2_m <= s1_m)

    def check_late_night(self, idx: int, item: dict) -> List[ReviewIssue]:
        """检查深夜安排"""
        issues = []
        start = self.parse_time(item.get("start_time", ""))
        end = self.parse_time(item.get("end_time", ""))

        if not start or not end:
            return issues

        # 检查是否在 00:00-06:00 之间
        start_m = self.time_to_minutes(start)
        end_m = self.time_to_minutes(end)

        # 检查时间段是否覆盖深夜
        late_start = 0  # 00:00
        late_end = 6 * 60  # 06:00

        # 处理跨天
        if end_m < start_m:
            end_m += 24 * 60

        # 检查重叠
        if (start_m < late_end and end_m > late_start) or \
           (start_m + 24*60 < late_end + 24*60 and end_m + 24*60 > late_start):
            issues.append(ReviewIssue(
                severity=IssueSeverity.ERROR,
                category="late_night",
                message=f"安排在深夜时段 ({item['start_time']}-{item['end_time']})",
                item_index=idx,
                item_title=item.get("title", "")
            ))

        return issues

    def check_time_reasonable(self, idx: int, item: dict) -> List[ReviewIssue]:
        """检查时间合理性"""
        issues = []
        start = self.parse_time(item.get("start_time", ""))
        end = self.parse_time(item.get("end_time", ""))
        title = item.get("title", "").lower()
        category = item.get("category", "")

        if not start or not end:
            issues.append(ReviewIssue(
                severity=IssueSeverity.ERROR,
                category="invalid_time",
                message=f"时间格式无效",
                item_index=idx,
                item_title=item.get("title", "")
            ))
            return issues

        # 检查时长
        duration = self.get_duration_minutes(start, end)
        if duration <= 0:
            issues.append(ReviewIssue(
                severity=IssueSeverity.ERROR,
                category="invalid_duration",
                message=f"结束时间必须晚于开始时间",
                item_index=idx,
                item_title=item.get("title", "")
            ))
        elif duration > self.max_event_duration:
            issues.append(ReviewIssue(
                severity=IssueSeverity.WARNING,
                category="too_long",
                message=f"时长过长（{duration}分钟），建议拆分",
                item_index=idx,
                item_title=item.get("title", "")
            ))

        # 根据类别检查时间
        hour = start.hour
        if category == "meal" or "早餐" in title or "午餐" in title or "晚餐" in title:
            if "早餐" in title:
                if not (6 <= hour <= 10):
                    issues.append(ReviewIssue(
                        severity=IssueSeverity.WARNING,
                        category="meal_time",
                        message=f"早餐时间不太合理（建议6:00-10:00）",
                        item_index=idx,
                        item_title=item.get("title", "")
                    ))
            elif "午餐" in title:
                if not (11 <= hour <= 14):
                    issues.append(ReviewIssue(
                        severity=IssueSeverity.WARNING,
                        category="meal_time",
                        message=f"午餐时间不太合理（建议11:00-14:00）",
                        item_index=idx,
                        item_title=item.get("title", "")
                    ))
            elif "晚餐" in title:
                if not (17 <= hour <= 21):
                    issues.append(ReviewIssue(
                        severity=IssueSeverity.WARNING,
                        category="meal_time",
                        message=f"晚餐时间不太合理（建议17:00-21:00）",
                        item_index=idx,
                        item_title=item.get("title", "")
                    ))

        if category == "exercise" or "运动" in title or "锻炼" in title:
            if not (6 <= hour <= 22):
                issues.append(ReviewIssue(
                    severity=IssueSeverity.WARNING,
                    category="exercise_time",
                    message=f"运动时间不太合理（建议6:00-22:00）",
                    item_index=idx,
                    item_title=item.get("title", "")
                ))

        if "睡觉" in title or "睡眠" in title or "睡前" in title:
            if not (20 <= hour <= 24 or 0 <= hour <= 1):
                issues.append(ReviewIssue(
                    severity=IssueSeverity.WARNING,
                    category="sleep_time",
                    message=f"睡觉时间不太合理",
                    item_index=idx,
                    item_title=item.get("title", "")
                ))

        if "起床" in title:
            if not (6 <= hour <= 9):
                issues.append(ReviewIssue(
                    severity=IssueSeverity.WARNING,
                    category="wake_time",
                    message=f"起床时间不太合理（建议6:00-9:00）",
                    item_index=idx,
                    item_title=item.get("title", "")
                ))

        return issues

    def check_overlaps(self, schedule: List[dict]) -> List[ReviewIssue]:
        """检查时间冲突"""
        issues = []
        n = len(schedule)

        for i in range(n):
            item1 = schedule[i]
            start1 = self.parse_time(item1.get("start_time", ""))
            end1 = self.parse_time(item1.get("end_time", ""))

            if not start1 or not end1:
                continue

            for j in range(i + 1, n):
                item2 = schedule[j]
                start2 = self.parse_time(item2.get("start_time", ""))
                end2 = self.parse_time(item2.get("end_time", ""))

                if not start2 or not end2:
                    continue

                if self.is_overlapping(start1, end1, start2, end2):
                    issues.append(ReviewIssue(
                        severity=IssueSeverity.ERROR,
                        category="overlap",
                        message=f"「{item1.get('title', '')}」({item1['start_time']}-{item1['end_time']}) 与 「{item2.get('title', '')}」({item2['start_time']}-{item2['end_time']}) 时间冲突",
                        item_index=i,
                    ))

        return issues

    def check_gaps_and_buffers(self, schedule: List[dict]) -> List[ReviewIssue]:
        """检查间隔和缓冲"""
        issues = []
        n = len(schedule)

        for i in range(n - 1):
            item1 = schedule[i]
            item2 = schedule[i + 1]

            end1 = self.parse_time(item1.get("end_time", ""))
            start2 = self.parse_time(item2.get("start_time", ""))

            if not end1 or not start2:
                continue

            end1_m = self.time_to_minutes(end1)
            start2_m = self.time_to_minutes(start2)

            gap = start2_m - end1_m

            # 处理跨天
            if gap < -12 * 60:
                gap += 24 * 60

            if gap < 0:
                # 重叠已在其他地方检查
                pass
            elif gap == 0:
                issues.append(ReviewIssue(
                    severity=IssueSeverity.WARNING,
                    category="no_buffer",
                    message=f"「{item1.get('title', '')}」和「{item2.get('title', '')}」之间没有缓冲时间",
                    item_index=i,
                ))
            elif gap < self.min_break_between:
                issues.append(ReviewIssue(
                    severity=IssueSeverity.INFO,
                    category="small_buffer",
                    message=f"「{item1.get('title', '')}」和「{item2.get('title', '')}」之间缓冲时间较短（{gap}分钟）",
                    item_index=i,
                ))
            elif gap > 120:
                issues.append(ReviewIssue(
                    severity=IssueSeverity.INFO,
                    category="large_gap",
                    message=f"「{item1.get('title', '')}」和「{item2.get('title', '')}」之间有较长空隙（{gap}分钟）",
                    item_index=i,
                ))

        return issues

    def check_completeness(self, schedule: List[dict]) -> List[ReviewIssue]:
        """检查规划完整性"""
        issues = []

        if not schedule:
            issues.append(ReviewIssue(
                severity=IssueSeverity.ERROR,
                category="empty",
                message="规划为空",
            ))
            return issues

        # 检查关键活动
        titles = [item.get("title", "").lower() for item in schedule]
        has_breakfast = any("早餐" in t for t in titles)
        has_lunch = any("午餐" in t for t in titles)
        has_dinner = any("晚餐" in t for t in titles)
        has_sleep = any("睡觉" in t or "睡眠" in t for t in titles)
        has_wake = any("起床" in t for t in titles)

        if not has_breakfast:
            issues.append(ReviewIssue(
                severity=IssueSeverity.INFO,
                category="missing",
                message="规划中缺少早餐安排",
            ))
        if not has_lunch:
            issues.append(ReviewIssue(
                severity=IssueSeverity.INFO,
                category="missing",
                message="规划中缺少午餐安排",
            ))
        if not has_dinner:
            issues.append(ReviewIssue(
                severity=IssueSeverity.INFO,
                category="missing",
                message="规划中缺少晚餐安排",
            ))

        return issues

    def review(self, plan: dict) -> Tuple[bool, List[ReviewIssue]]:
        """
        审查规划

        Returns:
            (是否通过, 问题列表)
        """
        issues: List[ReviewIssue] = []
        schedule = plan.get("schedule", [])

        # 检查完整性
        issues.extend(self.check_completeness(schedule))

        # 检查每个项目
        for idx, item in enumerate(schedule):
            issues.extend(self.check_late_night(idx, item))
            issues.extend(self.check_time_reasonable(idx, item))

        # 检查冲突
        issues.extend(self.check_overlaps(schedule))

        # 检查间隔
        issues.extend(self.check_gaps_and_buffers(schedule))

        # 按严重程度排序
        severity_order = {
            IssueSeverity.ERROR: 0,
            IssueSeverity.WARNING: 1,
            IssueSeverity.INFO: 2,
        }
        issues.sort(key=lambda x: severity_order.get(x.severity, 999))

        # 判断是否通过（没有 ERROR 级别的问题）
        has_errors = any(i.severity == IssueSeverity.ERROR for i in issues)
        return not has_errors, issues

    def get_summary(self, issues: List[ReviewIssue]) -> dict:
        """获取问题摘要"""
        error_count = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
        info_count = sum(1 for i in issues if i.severity == IssueSeverity.INFO)

        return {
            "total": len(issues),
            "errors": error_count,
            "warnings": warning_count,
            "infos": info_count,
            "passed": error_count == 0,
        }

    def issues_to_dict(self, issues: List[ReviewIssue]) -> List[dict]:
        """转换为字典格式"""
        return [
            {
                "severity": i.severity.value,
                "category": i.category,
                "message": i.message,
                "item_index": i.item_index,
                "item_title": i.item_title,
            }
            for i in issues
        ]
