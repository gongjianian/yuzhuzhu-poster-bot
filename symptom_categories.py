"""Hardcoded registry of symptom subcategories matching the WeChat mini-program
material_categories collection. IDs must match exactly what's in the database.
"""
from __future__ import annotations

LEVEL1_CATEGORIES = [
    {"id": "cat_piwei",  "name": "脾胃系列"},
    {"id": "cat_huxi",   "name": "呼吸道系列"},
    {"id": "cat_biyan",  "name": "鼻咽扁腺系列"},
]

ALL_SYMPTOM_CATEGORIES: list[dict] = [
    # ── 脾胃系列 ──────────────────────────────────────────────
    {
        "id":          "cat_pw_jstl",
        "name":        "积食停滞类",
        "level1_id":   "cat_piwei",
        "level1_name": "脾胃系列",
        "description": "吃不消、堵在肚里",
        "symptoms":    "积食腹胀、积食化热、积食夹湿",
    },
    {
        "id":          "cat_pw_pbyc",
        "name":        "排便异常类",
        "level1_id":   "cat_piwei",
        "level1_name": "脾胃系列",
        "description": "便秘、拉肚子",
        "symptoms":    "实热积滞便秘、脾胃虚寒便秘、受凉夹湿便稀",
    },
    {
        "id":          "cat_pw_pxsr",
        "name":        "脾虚湿弱类",
        "level1_id":   "cat_piwei",
        "level1_name": "脾胃系列",
        "description": "底子虚、没胃口",
        "symptoms":    "脾虚湿重、脾胃虚弱、食欲不振",
    },
    {
        "id":          "cat_pw_qjsh",
        "name":        "气机失和类",
        "level1_id":   "cat_piwei",
        "level1_name": "脾胃系列",
        "description": "气不顺、运转不协调",
        "symptoms":    "脾胃失和型地图舌、脾胃气滞腹胀",
    },
    # ── 呼吸道系列 ────────────────────────────────────────────
    {
        "id":          "cat_hx_shlq",
        "name":        "受寒初起",
        "level1_id":   "cat_huxi",
        "level1_name": "呼吸道系列",
        "description": "刚受凉、怕风怕冷",
        "symptoms":    "风寒发热咳嗽",
    },
    {
        "id":          "cat_hx_frsh",
        "name":        "风热上火",
        "level1_id":   "cat_huxi",
        "level1_name": "呼吸道系列",
        "description": "热气重、嗓子痛、黄痰",
        "symptoms":    "风热型发热、风热咳嗽黄痰",
    },
    {
        "id":          "cat_hx_rhcc",
        "name":        "寒热错杂",
        "level1_id":   "cat_huxi",
        "level1_name": "呼吸道系列",
        "description": "情况复杂、冷热不调",
        "symptoms":    "上热下寒咳嗽、冷热交替发作",
    },
    {
        "id":          "cat_hx_jktx",
        "name":        "久咳体虚与痰湿",
        "level1_id":   "cat_huxi",
        "level1_name": "呼吸道系列",
        "description": "感冒后期、脾胃虚弱",
        "symptoms":    "虚寒反复咳嗽、余热未除型久咳、痰湿型咳嗽",
    },
    # ── 鼻咽扁腺系列 ─────────────────────────────────────────
    {
        "id":          "cat_by_bybdl",
        "name":        "鼻炎鼻窦类",
        "level1_id":   "cat_biyan",
        "level1_name": "鼻咽扁腺系列",
        "description": "看鼻子、看鼻涕",
        "symptoms":    "过敏性鼻炎、反复型过敏鼻炎、积食夹痰型鼻炎、热性鼻窦炎",
    },
    {
        "id":          "cat_by_bdzdl",
        "name":        "扁腺肿大类",
        "level1_id":   "cat_biyan",
        "level1_name": "鼻咽扁腺系列",
        "description": "看嗓子、听睡觉动静",
        "symptoms":    "腺样体与鼻炎、扁桃体红肿反复",
    },
]

_CATEGORY_INDEX: dict[str, dict] = {c["id"]: c for c in ALL_SYMPTOM_CATEGORIES}


def get_category_by_id(category_id: str) -> dict | None:
    return _CATEGORY_INDEX.get(category_id)
