"""
UI设计规范系统
基于35个UI优化专业技能的完整设计规范
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from pathlib import Path
import json


@dataclass
class DesignTokens:
    """设计令牌 - 核心设计变量"""

    # 中性色分级规范 (技能五-2)
    neutral_colors: Dict[str, str] = field(default_factory=lambda: {
        'text_primary': '#333333',   # 核心正文
        'text_secondary': '#666666',  # 次要说明
        'text_muted': '#999999',      # 弱化辅助
        'border': '#CCCCCC',          # 分割线/边框
        'bg_base': '#E6E6E6',         # 背景底色
    })

    # 主辅色科学选型 (技能五-1)
    brand_colors: Dict[str, str] = field(default_factory=lambda: {
        'primary': '#6366F1',      # 主色 (高饱和高明度)
        'secondary': '#8B5CF6',    # 辅助色
        'success': '#10B981',      # 成功色
        'warning': '#F59E0B',       # 警告色
        'danger': '#EF4444',       # 危险色
        'info': '#06B6D4',          # 信息色
    })

    # 间距规范 (技能一-2)
    spacing: Dict[str, str] = field(default_factory=lambda: {
        'xs': '0.25rem',   # 4px
        'sm': '0.5rem',    # 8px
        'md': '1rem',      # 16px
        'lg': '1.5rem',    # 24px
        'xl': '2rem',      # 32px
        '2xl': '3rem',     # 48px
    })

    # 字号-行高对应规范 (技能二-1)
    typography: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        'xs': {'size': '0.75rem', 'lineHeight': '1.5'},   # 12px, 行高1.5
        'sm': {'size': '0.875rem', 'lineHeight': '1.5'},  # 14px, 行高1.5
        'base': {'size': '1rem', 'lineHeight': '1.6'},    # 16px, 行高1.6
        'lg': {'size': '1.125rem', 'lineHeight': '1.5'},  # 18px, 行高1.5
        'xl': {'size': '1.25rem', 'lineHeight': '1.4'},   # 20px, 行高1.4
        '2xl': {'size': '1.5rem', 'lineHeight': '1.3'},   # 24px, 行高1.3
        '3xl': {'size': '1.875rem', 'lineHeight': '1.2'},  # 30px, 行高1.2
    })

    # 圆角规范
    radii: Dict[str, str] = field(default_factory=lambda: {
        'sm': '0.375rem',   # 6px
        'md': '0.5rem',     # 8px
        'lg': '0.75rem',    # 12px
        'xl': '1rem',       # 16px
        '2xl': '1.5rem',    # 24px
        'full': '9999px',   # 完全圆角
    })

    # 投影统一规范 (技能一-3)
    shadows: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        'sm': {
            'offsetX': '0',
            'offsetY': '1px',
            'blur': '2px',
            'spread': '0',
            'color': 'rgba(0, 0, 0, 0.05)',
        },
        'md': {
            'offsetX': '0',
            'offsetY': '4px',
            'blur': '6px',
            'spread': '-1px',
            'color': 'rgba(0, 0, 0, 0.1)',
        },
        'lg': {
            'offsetX': '0',
            'offsetY': '10px',
            'blur': '15px',
            'spread': '-3px',
            'color': 'rgba(0, 0, 0, 0.1)',
        },
    })

    # 触控热区 (技能四-1)
    touch_target: str = '44px'

    # 动效时长 (技能四-5)
    transitions: Dict[str, str] = field(default_factory=lambda: {
        'fast': '150ms',
        'normal': '200ms',
        'slow': '300ms',
    })


@dataclass
class DesignGuidelines:
    """设计准则 - 35个技能的执行标准"""

    # 视觉布局优化 (技能一)
    visual_layout: Dict[str, Any] = field(default_factory=lambda: {
        'card_max_lines': 2,                    # 卡片文本默认显示2行
        'use_background_dividers': True,        # 用背景色替代分割线 (技能一-7)
        'unified_shadows': True,                # 统一投影规范
        'no_pure_black_text': True,             # 不使用纯黑文本 (技能一-4)
        'default_avatar_personalized': True,    # 默认头像人格化 (技能一-6)
        'image_consistency': True,               # 图片视觉统一 (技能一-5)
    })

    # 排版与文字优化 (技能二)
    typography_rules: Dict[str, Any] = field(default_factory=lambda: {
        'dynamic_line_height': True,             # 动态行高适配
        'form_labels_simplified': True,          # 表单标签简洁化 (技能二-2)
        'color_bg_text_contrast': True,          # 彩色背景文本适配 (技能二-3)
        'font_weight_hierarchy': True,           # 多字重字体层级 (技能二-4)
        'font_style_matched': True,              # 字体风格产品适配 (技能二-5)
        'image_text_mask': True,                  # 图片文字遮罩 (技能二-6)
        'text_depth_hierarchy': True,             # 文本深浅层级区分 (技能二-7)
    })

    # 表单体验优化 (技能三)
    form_ux: Dict[str, Any] = field(default_factory=lambda: {
        'minimize_fields': True,                  # 表单字段精简 (技能三-1)
        'keyboard_matching': True,                # 输入键盘精准匹配 (技能三-2)
        'real_time_validation': True,             # 表单实时验证 (技能三-7)
        'smart_defaults': True,                   # 智能默认值填充 (技能三-8)
        'long_form_split': True,                  # 长表单分步分页 (技能三-9)
    })

    # 交互与体验优化 (技能四)
    interaction_ux: Dict[str, Any] = field(default_factory=lambda: {
        'touch_target_min': 44,                   # 触控热区最小44px (技能四-1)
        'button_states': True,                     # 按钮多状态反馈 (技能四-2)
        'skeleton_loading': True,                  # 加载状态骨架屏 (技能四-3)
        'proximity_buttons': True,                # 操作按钮就近布局 (技能四-4)
        'smooth_transitions': True,               # 界面平滑过渡动效 (技能四-5)
        'progressive_onboarding': True,            # 用户渐进式引导 (技能四-6)
        'undo_irreversible': True,                # 不可逆操作撤销 (技能四-7)
    })

    # 色彩与细节精细化 (技能五)
    color_details: Dict[str, Any] = field(default_factory=lambda: {
        'primary_bright_saturated': True,         # 主色鲜亮饱和 (技能五-1)
        'neutral_gray_scale': True,               # 中性色分级规范 (技能五-2)
        'icon_style_unified': True,               # 图标风格统一化 (技能五-3)
        'password_visibility': True,               # 密码可视化优化 (技能五-4)
        'widescreen_optimized': True,              # 宽屏内容展示优化 (技能五-5)
    })


class DesignSystem:
    """完整的设计系统"""

    def __init__(self):
        self.tokens = DesignTokens()
        self.guidelines = DesignGuidelines()
        self.config_file = Path(__file__).parent.parent.parent / "data" / "design_system.json"
        self._load_custom_config()

    def _load_custom_config(self):
        """加载自定义配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'tokens' in data:
                        self._update_tokens(data['tokens'])
                    if 'guidelines' in data:
                        self._update_guidelines(data['guidelines'])
            except Exception as e:
                print(f"[DesignSystem] 加载配置失败: {e}")

    def _update_tokens(self, tokens_data: Dict[str, Any]):
        """更新设计令牌"""
        for key, value in tokens_data.items():
            if hasattr(self.tokens, key):
                if isinstance(value, dict):
                    current = getattr(self.tokens, key)
                    current.update(value)
                else:
                    setattr(self.tokens, key, value)

    def _update_guidelines(self, guidelines_data: Dict[str, Any]):
        """更新设计准则"""
        for key, value in guidelines_data.items():
            if hasattr(self.guidelines, key):
                if isinstance(value, dict):
                    current = getattr(self.guidelines, key)
                    current.update(value)
                else:
                    setattr(self.guidelines, key, value)

    def save_config(self):
        """保存配置"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'tokens': {
                'neutral_colors': self.tokens.neutral_colors,
                'brand_colors': self.tokens.brand_colors,
                'spacing': self.tokens.spacing,
                'typography': self.tokens.typography,
                'radii': self.tokens.radii,
                'shadows': self.tokens.shadows,
                'touch_target': self.tokens.touch_target,
                'transitions': self.tokens.transitions,
            },
            'guidelines': {
                'visual_layout': self.guidelines.visual_layout,
                'typography_rules': self.guidelines.typography_rules,
                'form_ux': self.guidelines.form_ux,
                'interaction_ux': self.guidelines.interaction_ux,
                'color_details': self.guidelines.color_details,
            }
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[DesignSystem] 保存配置失败: {e}")
            return False

    def get_css_variables(self) -> str:
        """生成CSS变量"""
        css = ":root {\n"

        # 中性色
        for name, color in self.tokens.neutral_colors.items():
            css += f"  --color-neutral-{name}: {color};\n"

        # 品牌色
        for name, color in self.tokens.brand_colors.items():
            css += f"  --color-brand-{name}: {color};\n"

        # 间距
        for name, value in self.tokens.spacing.items():
            css += f"  --spacing-{name}: {value};\n"

        # 字号
        for name, config in self.tokens.typography.items():
            css += f"  --font-size-{name}: {config['size']};\n"
            css += f"  --line-height-{name}: {config['lineHeight']};\n"

        # 圆角
        for name, value in self.tokens.radii.items():
            css += f"  --radius-{name}: {value};\n"

        # 触控热区
        css += f"  --touch-target: {self.tokens.touch_target};\n"

        # 动效
        for name, value in self.tokens.transitions.items():
            css += f"  --transition-{name}: {value};\n"

        css += "}\n"
        return css

    def get_skill_list(self) -> List[Dict[str, str]]:
        """获取35个技能列表"""
        return [
            {'category': 'visual_layout', 'name': '卡片信息层级优化', 'id': 'vl_card_hierarchy'},
            {'category': 'visual_layout', 'name': '界面留白布局设计', 'id': 'vl_whitespace'},
            {'category': 'visual_layout', 'name': '统一投影视觉规范', 'id': 'vl_unified_shadow'},
            {'category': 'visual_layout', 'name': '文本色彩柔和化优化', 'id': 'vl_soft_text_color'},
            {'category': 'visual_layout', 'name': '图片视觉统一性优化', 'id': 'vl_image_consistency'},
            {'category': 'visual_layout', 'name': '默认头像人格化设计', 'id': 'vl_personalized_avatar'},
            {'category': 'visual_layout', 'name': '区块分割视觉优化', 'id': 'vl_block_division'},

            {'category': 'typography', 'name': '动态行高适配排版', 'id': 'ty_dynamic_line_height'},
            {'category': 'typography', 'name': '表单标签简洁化排版', 'id': 'ty_form_label_simplify'},
            {'category': 'typography', 'name': '彩色背景文本适配', 'id': 'ty_color_bg_text'},
            {'category': 'typography', 'name': '多字重字体层级应用', 'id': 'ty_font_weight_hierarchy'},
            {'category': 'typography', 'name': '字体风格产品适配', 'id': 'ty_font_style_match'},
            {'category': 'typography', 'name': '图片文字遮罩优化', 'id': 'ty_image_text_mask'},
            {'category': 'typography', 'name': '文本深浅层级区分', 'id': 'ty_text_depth_hierarchy'},

            {'category': 'form_ux', 'name': '表单字段精简优化', 'id': 'fx_field_minimize'},
            {'category': 'form_ux', 'name': '输入键盘精准匹配', 'id': 'fx_keyboard_match'},
            {'category': 'form_ux', 'name': '表单实时验证反馈', 'id': 'fx_real_time_validation'},
            {'category': 'form_ux', 'name': '表单智能默认值填充', 'id': 'fx_smart_defaults'},
            {'category': 'form_ux', 'name': '长表单分步分页', 'id': 'fx_long_form_split'},

            {'category': 'interaction', 'name': '移动端触控热区优化', 'id': 'ix_touch_target'},
            {'category': 'interaction', 'name': '按钮多状态反馈设计', 'id': 'ix_button_states'},
            {'category': 'interaction', 'name': '加载状态骨架屏优化', 'id': 'ix_skeleton_loading'},
            {'category': 'interaction', 'name': '操作按钮就近布局', 'id': 'ix_proximity_buttons'},
            {'category': 'interaction', 'name': '界面平滑过渡动效', 'id': 'ix_smooth_transitions'},
            {'category': 'interaction', 'name': '用户渐进式引导', 'id': 'ix_progressive_onboarding'},
            {'category': 'interaction', 'name': '不可逆操作撤销', 'id': 'ix_undo_irreversible'},

            {'category': 'color_detail', 'name': '主辅色科学选型', 'id': 'cd_primary_color_selection'},
            {'category': 'color_detail', 'name': '中性色分级规范', 'id': 'cd_neutral_gray_scale'},
            {'category': 'color_detail', 'name': '图标风格统一化', 'id': 'cd_icon_style_unification'},
            {'category': 'color_detail', 'name': '密码可视化优化', 'id': 'cd_password_visibility'},
            {'category': 'color_detail', 'name': '宽屏内容展示优化', 'id': 'cd_widescreen_optimization'},
        ]


# 全局单例
_design_system: Optional[DesignSystem] = None


def get_design_system() -> DesignSystem:
    """获取设计系统单例"""
    global _design_system
    if _design_system is None:
        _design_system = DesignSystem()
    return _design_system
