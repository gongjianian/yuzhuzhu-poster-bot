import json
import pytest
from unittest.mock import patch, MagicMock
from models import ProductRecord, CategoryPosterTask, PosterScheme


def _make_task():
    products = [
        ProductRecord(record_id="r1", product_name="鸡内金泡浴",
                      benefits="消食化积", ingredients="鸡内金", product_line="五行泡浴",
                      asset_filename="jineijin.jpg"),
        ProductRecord(record_id="r2", product_name="金银花泡浴",
                      benefits="清热解毒", ingredients="金银花", product_line="五行泡浴",
                      asset_filename="jinyinhua.jpg"),
    ]
    return CategoryPosterTask(
        category_id="cat_pw_jstl",
        level1_category_id="cat_piwei",
        category_name="积食停滞类",
        product_line="五行泡浴",
        products=products,
    )


def _mock_scheme_json():
    return json.dumps({
        "scheme_name": "积食调理方案",
        "visual_style": "中草药极简风",
        "headline": "吃撑了？这套方案帮崽排积食",
        "subheadline": "鸡内金+金银花，消食化热两步走",
        "body_copy": ["消食化积", "清热不上火", "宝宝吃饭香"],
        "cta": "查看使用方法",
        "image_prompt": "两瓶草本泡浴产品...",
        "aspect_ratio": "3:4",
    })


@patch("category_content_generator._build_client")
def test_generate_category_content_returns_scheme(mock_build):
    from category_content_generator import generate_category_poster_content

    mock_client = MagicMock()
    mock_build.return_value = mock_client
    msg = MagicMock()
    msg.content = _mock_scheme_json()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=msg)]
    )

    scheme = generate_category_poster_content(_make_task())
    assert isinstance(scheme, PosterScheme)
    assert scheme.headline
    assert scheme.image_prompt
    assert len(scheme.body_copy) > 0


@patch("category_content_generator._build_client")
def test_generate_category_content_includes_product_names_in_prompt(mock_build):
    from category_content_generator import generate_category_poster_content

    mock_client = MagicMock()
    mock_build.return_value = mock_client
    msg = MagicMock()
    msg.content = _mock_scheme_json()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=msg)]
    )

    generate_category_poster_content(_make_task())

    call_args = mock_client.chat.completions.create.call_args
    prompt_text = call_args[1]["messages"][0]["content"]
    assert "鸡内金泡浴" in prompt_text
    assert "积食停滞类" in prompt_text
