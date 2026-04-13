import threading
import time
from datetime import datetime
from typing import Callable, List, Dict, Any
import random


class ScheduledJob:
    def __init__(self, hour: int, minute: int, func: Callable, *args, **kwargs):
        self.hour = hour
        self.minute = minute
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.last_run: datetime | None = None

    def should_run(self, now: datetime) -> bool:
        if now.hour != self.hour or now.minute != self.minute:
            return False
        if self.last_run and self.last_run.date() == now.date():
            return False
        return True

    def run(self):
        self.last_run = datetime.now()
        thread = threading.Thread(target=self.func, args=self.args, kwargs=self.kwargs, daemon=True)
        thread.start()


class DailyScheduler:
    def __init__(self):
        self._running = False
        self._thread = None
        self._jobs: List[ScheduledJob] = []

    def add_daily_job(self, hour: int, minute: int, func: Callable, *args, **kwargs):
        """添加每日定时任务"""
        job = ScheduledJob(hour, minute, func, *args, **kwargs)
        self._jobs.append(job)
        print(f"[定时任务] 已添加每日 {hour:02d}:{minute:02d} 任务: {func.__name__}")
        return job

    def start(self):
        """启动调度器"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[定时任务] 调度器已启动")

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[定时任务] 调度器已停止")

    def _loop(self):
        """调度器主循环"""
        while self._running:
            now = datetime.now()
            for job in self._jobs:
                if job.should_run(now):
                    print(f"[定时任务] 执行: {job.func.__name__}")
                    job.run()
            time.sleep(30)  # 每30秒检查一次

    def run_now(self, func: Callable, *args, **kwargs):
        """立即运行一个任务（用于测试）"""
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()


# 全局单例
_scheduler = None


def get_scheduler() -> DailyScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = DailyScheduler()
    return _scheduler
