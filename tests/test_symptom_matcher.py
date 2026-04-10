import json
import pytest
from unittest.mock import patch, MagicMock
from models import ProductRecord, CategoryPosterTask


def _make_products():
    return [
        ProductRecord(record_id="r1", product_name="鸡内金泡浴", benefits="消食化积，健脾助运", product_line="五行泡浴"),
        ProductRecord(record_id="r2", product_name="金银花泡浴", benefits="清热解毒，疏散风热", product_line="五行泡浴"),
        ProductRecord(record_id="r3", product_name="积食贴", benefits="消食化积外敷", product_line="靶向敷贴"),
        ProductRecord(record_id="r4", product_name="薰衣草精油", benefits="助眠安神", product_line="精油系列"),
    ]


def _mock_ai_response(groups: dict) -> str:
    """groups: {"五行泡浴": ["r1", "r2"], "靶向敷贴": ["r3"]}"""
    return json.dumps({"groups": [
        {"product_line": pl, "product_ids": ids, "reason": "测试"}
        for pl, ids in groups.items()
    ]})


@patch("symptom_matcher._build_client")
def test_match_returns_category_tasks(mock_build):
    from symptom_matcher import match_products_to_symptom
    from symptom_categories import ALL_SYMPTOM_CATEGORIES

    mock_client = MagicMock()
    mock_build.return_value = mock_client
    msg = MagicMock()
    msg.content = _mock_ai_response({"五行泡浴": ["r1", "r2"], "靶向敷贴": ["r3"]})
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=msg)]
    )

    category = ALL_SYMPTOM_CATEGORIES[0]  # 积食停滞类
    tasks = match_products_to_symptom(category, _make_products())

    assert len(tasks) == 2
    lines = {t.product_line for t in tasks}
    assert "五行泡浴" in lines
    assert "靶向敷贴" in lines


@patch("symptom_matcher._build_client")
def test_match_caps_products_at_three(mock_build):
    from symptom_matcher import match_products_to_symptom
    from symptom_categories import ALL_SYMPTOM_CATEGORIES

    mock_client = MagicMock()
    mock_build.return_value = mock_client
    msg = MagicMock()
    # AI returns 4 products — should be capped to 3
    msg.content = _mock_ai_response({"五行泡浴": ["r1", "r2", "r3", "r4"]})
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=msg)]
    )

    category = ALL_SYMPTOM_CATEGORIES[0]
    products = _make_products()
    tasks = match_products_to_symptom(category, products)

    assert len(tasks[0].products) <= 3


@patch("symptom_matcher._build_client")
def test_match_returns_empty_when_no_match(mock_build):
    from symptom_matcher import match_products_to_symptom
    from symptom_categories import ALL_SYMPTOM_CATEGORIES

    mock_client = MagicMock()
    mock_build.return_value = mock_client
    msg = MagicMock()
    msg.content = json.dumps({"groups": []})
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=msg)]
    )

    category = ALL_SYMPTOM_CATEGORIES[0]
    tasks = match_products_to_symptom(category, _make_products())
    assert tasks == []
