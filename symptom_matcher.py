"""Match all Feishu products to a symptom subcategory using Gemini.

Returns a list of CategoryPosterTask — one per matched product line.
Each task contains 1-3 products that AI selected as best for that category.
"""
from __future__ import annotations

import json
import os
import re

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from models import CategoryPosterTask, ProductRecord

load_dotenv()

_MAX_PRODUCTS_PER_GROUP = 3

_MATCH_PROMPT = """你是一位中医育儿产品搭配专家。

## 症状分类
名称：{category_name}
描述：{description}
典型症状：{symptoms}

## 产品库
{product_list}

## 任务
从产品库中找出最适合治疗上述症状的产品，按产品线分组。
规则：
1. 每个产品线最多选 3 个产品
2. 只选与症状高度相关的产品，不相关的不选
3. 同一产品线的产品放在同一组
4. 如果某产品线没有合适的产品，不要创建该组

输出严格 JSON，不要任何 markdown 或解释：
{{"groups": [{{"product_line": "产品线名称", "product_ids": ["id1", "id2"], "reason": "简短原因"}}]}}
"""


def _build_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url=os.getenv("GEMINI_API_BASE", "https://api.buxianliang.fun/v1"),
    )


def _resolve_copy_model() -> str:
    try:
        from dashboard.services import runtime_settings
        model = runtime_settings.get_copy_model()
    except Exception as exc:
        logger.debug("runtime_settings unavailable, using env: {}", exc)
        model = os.getenv("GEMINI_COPY_MODEL", "gemini-3.1-pro-preview")
    if model.startswith("models/"):
        model = model[len("models/"):]
    return model


def _format_product_list(products: list[ProductRecord]) -> str:
    lines = []
    for p in products:
        lines.append(
            f"- ID:{p.record_id} | 名称:{p.product_name} | 产品线:{p.product_line}"
            f" | 功效:{p.benefits} | 成分:{p.ingredients}"
        )
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON found in response: {text[:300]}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    reraise=True,
)
def match_products_to_symptom(
    category: dict,
    all_products: list[ProductRecord],
) -> list[CategoryPosterTask]:
    """Ask Gemini to match products from all_products to the given symptom category.

    Returns one CategoryPosterTask per matched product line (max 3 products each).
    Returns empty list if no products match this category.
    """
    if not all_products:
        return []

    client = _build_client()
    model = _resolve_copy_model()

    prompt = _MATCH_PROMPT.format(
        category_name=category["name"],
        description=category["description"],
        symptoms=category["symptoms"],
        product_list=_format_product_list(all_products),
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    content = resp.choices[0].message.content or ""

    try:
        data = _extract_json(content)
    except (ValueError, json.JSONDecodeError) as e:
        logger.error("symptom_matcher JSON parse error for {}: {}", category["name"], e)
        return []

    product_index = {p.record_id: p for p in all_products}
    tasks: list[CategoryPosterTask] = []

    for group in data.get("groups", []):
        product_line = group.get("product_line", "")
        product_ids = group.get("product_ids", [])[:_MAX_PRODUCTS_PER_GROUP]
        matched = [product_index[pid] for pid in product_ids if pid in product_index]

        if not matched:
            logger.warning(
                "symptom_matcher: group '{}' returned no valid product IDs for {}",
                product_line, category["name"],
            )
            continue

        tasks.append(CategoryPosterTask(
            category_id=category["id"],
            level1_category_id=category["level1_id"],
            category_name=category["name"],
            product_line=product_line,
            products=matched,
        ))
        logger.info(
            "matched {} × {} → {} products",
            category["name"], product_line, len(matched),
        )

    return tasks
