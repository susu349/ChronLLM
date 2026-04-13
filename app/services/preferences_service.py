import json
from typing import Any
from app.database import SessionLocal
from app.models import UserPreference


# 管家风格预设
BUTLER_STYLES = {
    "classic": {
        "name": "经典管家",
        "description": "专业、稳重、优雅的老派管家",
        "greeting": "您好，{user_name}。",
        "call_user": "{user_name}",
        "self_call": "我",
        "tone": "professional",
        "emoji": "🎩",
        "color": "#334155",
    },
    "catgirl": {
        "name": "猫娘",
        "description": "可爱、活泼、带有喵~尾音的猫娘",
        "greeting": "{user_name}，喵~！",
        "call_user": "{user_name}大人",
        "self_call": "人家",
        "tone": "cute",
        "emoji": "🐱",
        "color": "#ec4899",
    },
    "maid": {
        "name": "女仆",
        "description": "恭敬、温柔、周到的女仆",
        "greeting": "欢迎回来，{user_name}大人！",
        "call_user": "{user_name}大人",
        "self_call": "女仆",
        "tone": "polite",
        "emoji": "🎀",
        "color": "#8b5cf6",
    },
    "butler": {
        "name": "执事",
        "description": "英式管家风格，完美、优雅",
        "greeting": "日安，{user_name}。",
        "call_user": "老爷/夫人",
        "self_call": "在下",
        "tone": "elegant",
        "emoji": "☕",
        "color": "#0f1729",
    },
    "tsundere": {
        "name": "傲娇",
        "description": "嘴上不饶人，其实很关心您",
        "greeting": "哼、才、才不是特地等你呢！",
        "call_user": "那个...{user_name}",
        "self_call": "我、我才不是...",
        "tone": "tsundere",
        "emoji": "😤",
        "color": "#f59e0b",
    },
    "sister": {
        "name": "姐姐",
        "description": "温柔、体贴、包容的大姐姐",
        "greeting": "回来啦，{user_name}～",
        "call_user": "{user_name}酱",
        "self_call": "姐姐",
        "tone": "gentle",
        "emoji": "🌸",
        "color": "#06b6d4",
    },
    "samurai": {
        "name": "武士",
        "description": "忠诚、刚毅、守信的武士",
        "greeting": "主君！恭候多时！",
        "call_user": "主君",
        "self_call": "在下",
        "tone": "samurai",
        "emoji": "⚔️",
        "color": "#1e293b",
    },
    "robot": {
        "name": "AI助手",
        "description": "高效、精准、不带感情的AI",
        "greeting": "系统启动。欢迎，用户{user_name}。",
        "call_user": "用户{user_name}",
        "self_call": "本系统",
        "tone": "robot",
        "emoji": "🤖",
        "color": "#38bdf8",
    },
}


# 用户身份预设
IDENTITY_PRESETS = {
    "student": {
        "name": "学生",
        "description": "早八晚十，学习为主",
        "wake_up_time": "06:30",
        "breakfast_time": "07:00",
        "work_start_time": "08:00",
        "lunch_time": "12:00",
        "work_end_time": "18:00",
        "dinner_time": "18:30",
        "bed_time": "23:00",
        "buffer_minutes": "10",
        "preferred_work_block": "50",
        "include_exercise": "true",
        "exercise_duration": "45",
        "exercise_time": "evening",
        "deep_work_first": "true",
        "pomodoro_enabled": "true",
        "work_label": "学习",
    },
    "worker": {
        "name": "上班族",
        "description": "朝九晚五，工作为重",
        "wake_up_time": "07:30",
        "breakfast_time": "08:00",
        "work_start_time": "09:00",
        "lunch_time": "12:30",
        "work_end_time": "18:00",
        "dinner_time": "19:00",
        "bed_time": "23:30",
        "buffer_minutes": "15",
        "preferred_work_block": "60",
        "include_exercise": "true",
        "exercise_duration": "45",
        "exercise_time": "evening",
        "deep_work_first": "true",
        "pomodoro_enabled": "false",
        "work_label": "工作",
    },
    "freelancer": {
        "name": "自由职业者",
        "description": "灵活安排，效率优先",
        "wake_up_time": "08:00",
        "breakfast_time": "08:30",
        "work_start_time": "09:30",
        "lunch_time": "12:30",
        "work_end_time": "18:30",
        "dinner_time": "19:00",
        "bed_time": "00:00",
        "buffer_minutes": "10",
        "preferred_work_block": "90",
        "include_exercise": "true",
        "exercise_duration": "60",
        "exercise_time": "morning",
        "deep_work_first": "true",
        "pomodoro_enabled": "false",
        "work_label": "工作",
    },
    "retired": {
        "name": "退休/悠闲",
        "description": "享受生活，健康第一",
        "wake_up_time": "07:00",
        "breakfast_time": "07:30",
        "work_start_time": "08:30",
        "lunch_time": "12:00",
        "work_end_time": "17:00",
        "dinner_time": "18:00",
        "bed_time": "22:00",
        "buffer_minutes": "20",
        "preferred_work_block": "45",
        "include_exercise": "true",
        "exercise_duration": "30",
        "exercise_time": "morning",
        "deep_work_first": "false",
        "pomodoro_enabled": "false",
        "work_label": "活动",
    },
}


DEFAULT_PREFERENCES = {
    # 用户身份和管家风格
    "user_identity": "worker",  # 默认上班族
    "butler_style": "classic",  # 默认经典管家

    # 作息时间
    "wake_up_time": "07:30",
    "breakfast_time": "08:00",
    "work_start_time": "09:00",
    "lunch_time": "12:30",
    "work_end_time": "18:00",
    "dinner_time": "19:00",
    "bed_time": "23:30",

    # 习惯设置
    "buffer_minutes": "15",  # 事件间缓冲时间
    "preferred_work_block": "60",  # 偏好工作块时长（分钟）
    "include_exercise": "true",  # 是否安排运动
    "exercise_duration": "45",  # 运动时长（分钟）
    "exercise_time": "evening",  # 运动时间: morning/evening

    # 工作/学习设置
    "deep_work_first": "true",  # 是否优先安排深度工作
    "pomodoro_enabled": "false",  # 是否启用番茄钟模式
    "work_label": "工作",  # 工作/学习标签

    # 自定义身份（JSON格式）
    "custom_identity": "{}",
    # 自定义管家风格（JSON格式）
    "custom_butler_style": "{}",
}


class PreferencesService:
    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        self.db.close()

    def get_all(self) -> dict:
        """获取所有偏好设置"""
        prefs = dict(DEFAULT_PREFERENCES)
        for pref in self.db.query(UserPreference).all():
            prefs[pref.key] = pref.value
        return prefs

    def get(self, key: str, default: str = None) -> str:
        """获取单个偏好"""
        pref = self.db.query(UserPreference).filter(UserPreference.key == key).first()
        if pref:
            return pref.value
        return DEFAULT_PREFERENCES.get(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        """获取整数偏好"""
        val = self.get(key)
        try:
            return int(val) if val else default
        except ValueError:
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """获取布尔偏好"""
        val = self.get(key)
        if val is None:
            return default
        return val.lower() in ("true", "yes", "1", "on")

    def get_json(self, key: str, default: dict = None) -> dict:
        """获取JSON偏好"""
        val = self.get(key)
        if val:
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                pass
        return default or {}

    def set(self, key: str, value: str):
        """设置偏好"""
        pref = self.db.query(UserPreference).filter(UserPreference.key == key).first()
        if pref:
            pref.value = str(value)
        else:
            pref = UserPreference(key=key, value=str(value))
            self.db.add(pref)
        self.db.commit()
        return pref

    def set_json(self, key: str, value: dict):
        """设置JSON偏好"""
        self.set(key, json.dumps(value, ensure_ascii=False))

    def set_batch(self, settings: dict):
        """批量设置"""
        for key, value in settings.items():
            # 允许设置所有预设中的键
            all_keys = set(DEFAULT_PREFERENCES.keys())
            for preset in IDENTITY_PRESETS.values():
                all_keys.update(preset.keys())
            for style in BUTLER_STYLES.values():
                all_keys.update(style.keys())

            if key in all_keys:
                self.set(key, str(value))
        self.db.commit()

    def apply_identity_preset(self, identity: str) -> bool:
        """应用用户身份预设"""
        if identity not in IDENTITY_PRESETS:
            return False

        preset = IDENTITY_PRESETS[identity]
        for key, value in preset.items():
            self.set(key, str(value))
        self.set("user_identity", identity)
        return True

    def apply_butler_style(self, style: str, user_name: str = "少爷") -> bool:
        """应用管家风格"""
        if style not in BUTLER_STYLES:
            return False

        preset = BUTLER_STYLES[style]
        # 保存风格配置
        for key, value in preset.items():
            self.set(f"style_{key}", str(value))
        self.set("butler_style", style)
        return True

    def get_butler_style_config(self) -> dict:
        """获取管家风格配置（合并默认和自定义）"""
        style = self.get("butler_style", "classic")
        config = dict(BUTLER_STYLES.get(style, BUTLER_STYLES["classic"]))

        # 应用自定义配置
        custom_config = self.get_json("custom_butler_style", {})
        config.update(custom_config)

        # 替换用户称呼
        user_name = self.get("user_name", "少爷")
        for key in ["greeting", "call_user"]:
            if key in config:
                config[key] = config[key].replace("{user_name}", user_name)

        return config

    def get_identity_presets(self) -> dict:
        """获取所有身份预设"""
        return IDENTITY_PRESETS

    def get_butler_styles(self) -> dict:
        """获取所有管家风格"""
        return BUTLER_STYLES

    def save_custom_identity(self, config: dict) -> bool:
        """保存自定义身份"""
        self.set_json("custom_identity", config)
        return True

    def save_custom_butler_style(self, config: dict) -> bool:
        """保存自定义管家风格"""
        self.set_json("custom_butler_style", config)
        return True
