"""食谱服务 - 提供食谱和每周营养推荐"""

import json
import random
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.database import SessionLocal
from app.models import Recipe, MealPlan


# 默认食谱库
DEFAULT_RECIPES = [
    # 早餐
    {
        "name": "燕麦牛奶粥配水果",
        "description": "营养丰富的快手早餐，富含膳食纤维和维生素",
        "ingredients": json.dumps([
            {"name": "燕麦片", "amount": "50g"},
            {"name": "牛奶", "amount": "250ml"},
            {"name": "蓝莓", "amount": "30g"},
            {"name": "香蕉", "amount": "半根"},
            {"name": "蜂蜜", "amount": "适量"},
        ], ensure_ascii=False),
        "instructions": json.dumps([
            "将燕麦片放入碗中",
            "加入牛奶，微波炉加热2分钟",
            "放入切片的香蕉和蓝莓",
            "淋上蜂蜜即可",
        ], ensure_ascii=False),
        "prep_time": 5,
        "cook_time": 2,
        "servings": 1,
        "difficulty": "easy",
        "tags": "健康,快手,早餐,低卡",
        "cuisine": "西式",
        "meal_type": "breakfast",
        "calories": 280,
        "protein": 12,
        "carbs": 45,
        "fat": 6,
        "fiber": 5,
    },
    {
        "name": "中式豆浆油条",
        "description": "经典中式早餐，豆浆配油条",
        "ingredients": json.dumps([
            {"name": "油条", "amount": "2根"},
            {"name": "黄豆", "amount": "50g"},
            {"name": "水", "amount": "500ml"},
            {"name": "白糖", "amount": "适量"},
        ], ensure_ascii=False),
        "instructions": json.dumps([
            "黄豆提前泡发",
            "用豆浆机打成豆浆",
            "豆浆过滤后煮沸",
            "油条切段，配热豆浆食用",
        ], ensure_ascii=False),
        "prep_time": 10,
        "cook_time": 15,
        "servings": 2,
        "difficulty": "medium",
        "tags": "中式,早餐,经典",
        "cuisine": "中式",
        "meal_type": "breakfast",
        "calories": 450,
        "protein": 18,
        "carbs": 55,
        "fat": 18,
        "fiber": 4,
    },
    # 午餐
    {
        "name": "鸡胸肉蔬菜沙拉",
        "description": "低脂高蛋白的健康午餐，适合健身人士",
        "ingredients": json.dumps([
            {"name": "鸡胸肉", "amount": "150g"},
            {"name": "生菜", "amount": "100g"},
            {"name": "番茄", "amount": "1个"},
            {"name": "黄瓜", "amount": "半根"},
            {"name": "紫甘蓝", "amount": "50g"},
            {"name": "橄榄油", "amount": "1勺"},
            {"name": "柠檬汁", "amount": "适量"},
        ], ensure_ascii=False),
        "instructions": json.dumps([
            "鸡胸肉用盐、黑胡椒腌制15分钟",
            "平底锅煎熟鸡胸肉，切片",
            "所有蔬菜洗净切好",
            "摆入盘中，放上鸡肉片",
            "淋上橄榄油和柠檬汁",
        ], ensure_ascii=False),
        "prep_time": 20,
        "cook_time": 10,
        "servings": 1,
        "difficulty": "easy",
        "tags": "健康,低脂,高蛋白,健身,沙拉",
        "cuisine": "西式",
        "meal_type": "lunch",
        "calories": 320,
        "protein": 35,
        "carbs": 15,
        "fat": 12,
        "fiber": 6,
    },
    {
        "name": "番茄炒蛋盖饭",
        "description": "经典家常菜，简单美味",
        "ingredients": json.dumps([
            {"name": "番茄", "amount": "2个"},
            {"name": "鸡蛋", "amount": "3个"},
            {"name": "米饭", "amount": "2碗"},
            {"name": "葱", "amount": "适量"},
            {"name": "盐", "amount": "适量"},
            {"name": "糖", "amount": "少许"},
        ], ensure_ascii=False),
        "instructions": json.dumps([
            "番茄切块，鸡蛋打散",
            "热锅冷油，炒散鸡蛋盛出",
            "锅中加油，炒番茄至出汁",
            "加入盐和少许糖调味",
            "倒入鸡蛋翻炒均匀",
            "浇在米饭上即可",
        ], ensure_ascii=False),
        "prep_time": 10,
        "cook_time": 10,
        "servings": 2,
        "difficulty": "easy",
        "tags": "家常菜,快手,下饭菜,经典",
        "cuisine": "中式",
        "meal_type": "lunch",
        "calories": 420,
        "protein": 18,
        "carbs": 58,
        "fat": 14,
        "fiber": 3,
    },
    # 晚餐
    {
        "name": "清蒸鲈鱼",
        "description": "清淡鲜美，营养丰富的鱼肉料理",
        "ingredients": json.dumps([
            {"name": "鲈鱼", "amount": "1条（约500g）"},
            {"name": "葱", "amount": "2根"},
            {"name": "姜", "amount": "1块"},
            {"name": "蒸鱼豉油", "amount": "2勺"},
            {"name": "料酒", "amount": "1勺"},
        ], ensure_ascii=False),
        "instructions": json.dumps([
            "鲈鱼处理干净，两面划几刀",
            "用料酒腌制10分钟",
            "鱼身放上姜片和葱段",
            "水开后蒸8-10分钟",
            "倒掉蒸出的水，放上新鲜葱丝",
            "淋上蒸鱼豉油，浇热油即可",
        ], ensure_ascii=False),
        "prep_time": 15,
        "cook_time": 12,
        "servings": 2,
        "difficulty": "medium",
        "tags": "清淡,鱼肉,健康,高蛋白",
        "cuisine": "中式",
        "meal_type": "dinner",
        "calories": 220,
        "protein": 38,
        "carbs": 3,
        "fat": 6,
        "fiber": 0,
    },
    {
        "name": "香煎牛排配时蔬",
        "description": "西餐厅级别的美味晚餐",
        "ingredients": json.dumps([
            {"name": "西冷牛排", "amount": "200g"},
            {"name": "西兰花", "amount": "100g"},
            {"name": "胡萝卜", "amount": "1根"},
            {"name": "土豆", "amount": "1个"},
            {"name": "黄油", "amount": "20g"},
            {"name": "蒜末", "amount": "适量"},
        ], ensure_ascii=False),
        "instructions": json.dumps([
            "牛排室温回温，用盐和黑胡椒调味",
            "西兰花切小朵，胡萝卜切片，土豆切块",
            "时蔬焯水备用",
            "热锅，牛排每面煎3-4分钟",
            "放入黄油、蒜末增香",
            "牛排静置5分钟后切片",
            "与时蔬一起装盘",
        ], ensure_ascii=False),
        "prep_time": 20,
        "cook_time": 15,
        "servings": 1,
        "difficulty": "medium",
        "tags": "牛排,西餐,高蛋白",
        "cuisine": "西式",
        "meal_type": "dinner",
        "calories": 480,
        "protein": 42,
        "carbs": 25,
        "fat": 24,
        "fiber": 5,
    },
]


class RecipeService:
    """食谱服务"""

    def __init__(self):
        self.db = SessionLocal()
        self._init_default_recipes()

    def close(self):
        self.db.close()

    def _init_default_recipes(self):
        """初始化默认食谱"""
        count = self.db.query(Recipe).count()
        if count == 0:
            print("[食谱] 初始化默认食谱库")
            for recipe_data in DEFAULT_RECIPES:
                recipe = Recipe(**recipe_data)
                self.db.add(recipe)
            self.db.commit()

    def get_all_recipes(self, meal_type: Optional[str] = None,
                       tag: Optional[str] = None,
                       cuisine: Optional[str] = None) -> List[Recipe]:
        """获取所有食谱"""
        query = self.db.query(Recipe)

        if meal_type:
            query = query.filter(Recipe.meal_type == meal_type)
        if cuisine:
            query = query.filter(Recipe.cuisine == cuisine)
        if tag:
            query = query.filter(Recipe.tags.like(f"%{tag}%"))

        return query.order_by(Recipe.name).all()

    def get_recipe(self, recipe_id: int) -> Optional[Recipe]:
        """获取单个食谱"""
        return self.db.query(Recipe).filter(Recipe.id == recipe_id).first()

    def search_recipes(self, keyword: str) -> List[Recipe]:
        """搜索食谱"""
        keyword = f"%{keyword}%"
        return self.db.query(Recipe).filter(
            (Recipe.name.like(keyword)) |
            (Recipe.description.like(keyword)) |
            (Recipe.tags.like(keyword))
        ).all()

    def add_custom_recipe(self, recipe_data: Dict[str, Any]) -> Recipe:
        """添加自定义食谱"""
        recipe_data["is_custom"] = True
        recipe = Recipe(**recipe_data)
        self.db.add(recipe)
        self.db.commit()
        self.db.refresh(recipe)
        return recipe

    def delete_recipe(self, recipe_id: int) -> bool:
        """删除食谱（只能删除自定义的）"""
        recipe = self.get_recipe(recipe_id)
        if recipe and recipe.is_custom:
            self.db.delete(recipe)
            self.db.commit()
            return True
        return False

    def generate_weekly_plan(self, week_start: Optional[date] = None) -> Dict[str, Any]:
        """生成每周饮食计划"""
        if week_start is None:
            # 找到本周一
            today = date.today()
            week_start = today - timedelta(days=today.weekday())

        # 按餐次分类食谱
        breakfasts = self.get_all_recipes(meal_type="breakfast")
        lunches = self.get_all_recipes(meal_type="lunch")
        dinners = self.get_all_recipes(meal_type="dinner")

        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        plan = {}
        total_nutrition = {
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
            "fiber": 0,
        }

        for i, day in enumerate(days):
            current_date = week_start + timedelta(days=i)
            date_str = current_date.isoformat()

            # 随机选择食谱
            breakfast = random.choice(breakfasts) if breakfasts else None
            lunch = random.choice(lunches) if lunches else None
            dinner = random.choice(dinners) if dinners else None

            plan[date_str] = {
                "day_name": day,
                "date": date_str,
                "breakfast": self._recipe_to_dict(breakfast) if breakfast else None,
                "lunch": self._recipe_to_dict(lunch) if lunch else None,
                "dinner": self._recipe_to_dict(dinner) if dinner else None,
            }

            # 累计营养
            for meal in [breakfast, lunch, dinner]:
                if meal:
                    total_nutrition["calories"] += meal.calories
                    total_nutrition["protein"] += meal.protein
                    total_nutrition["carbs"] += meal.carbs
                    total_nutrition["fat"] += meal.fat
                    total_nutrition["fiber"] += meal.fiber

        # 计算平均每日营养
        avg_nutrition = {
            key: round(value / 7)
            for key, value in total_nutrition.items()
        }

        return {
            "week_start": week_start.isoformat(),
            "plan": plan,
            "total_nutrition": total_nutrition,
            "avg_daily_nutrition": avg_nutrition,
        }

    def save_weekly_plan(self, week_start: str, plan_data: Dict[str, Any]) -> MealPlan:
        """保存每周计划"""
        existing = self.db.query(MealPlan).filter(MealPlan.week_start == week_start).first()
        if existing:
            existing.plan_data = json.dumps(plan_data, ensure_ascii=False)
        else:
            meal_plan = MealPlan(
                week_start=week_start,
                plan_data=json.dumps(plan_data, ensure_ascii=False),
            )
            self.db.add(meal_plan)
        self.db.commit()
        return existing or meal_plan

    def get_weekly_plan(self, week_start: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取保存的周计划"""
        if week_start is None:
            today = date.today()
            week_start_date = today - timedelta(days=today.weekday())
            week_start = week_start_date.isoformat()

        meal_plan = self.db.query(MealPlan).filter(MealPlan.week_start == week_start).first()
        if meal_plan:
            return {
                "week_start": meal_plan.week_start,
                "plan": json.loads(meal_plan.plan_data) if meal_plan.plan_data else {},
                "notes": meal_plan.notes,
                "created_at": meal_plan.created_at.isoformat(),
            }
        return None

    def _recipe_to_dict(self, recipe: Recipe) -> Dict[str, Any]:
        """食谱转字典"""
        return {
            "id": recipe.id,
            "name": recipe.name,
            "description": recipe.description,
            "ingredients": json.loads(recipe.ingredients) if recipe.ingredients else [],
            "instructions": json.loads(recipe.instructions) if recipe.instructions else [],
            "prep_time": recipe.prep_time,
            "cook_time": recipe.cook_time,
            "servings": recipe.servings,
            "difficulty": recipe.difficulty,
            "tags": recipe.tags.split(",") if recipe.tags else [],
            "cuisine": recipe.cuisine,
            "meal_type": recipe.meal_type,
            "nutrition": {
                "calories": recipe.calories,
                "protein": recipe.protein,
                "carbs": recipe.carbs,
                "fat": recipe.fat,
                "fiber": recipe.fiber,
            },
        }

    def to_dict(self, recipe: Recipe) -> Dict[str, Any]:
        """食谱转字典（外部调用）"""
        return self._recipe_to_dict(recipe)
