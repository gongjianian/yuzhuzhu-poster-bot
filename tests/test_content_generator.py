import json
import pytest
from unittest.mock import patch, MagicMock
from models import ProductRecord, PosterScheme
from content_generator import generate_poster_content


def _make_record():
    return ProductRecord(
        record_id="rec001",
        product_name="玻尿酸精华液",
        ingredients="透明质酸钠",
        benefits="深层补水，锁水保湿",
        xiaohongshu_topics="秋冬护肤",
        visual_style="极简扁平",
        brand_colors="#FFFFFF",
        asset_filename="product_a.png",
    )


def _mock_scheme_response():
    return json.dumps({
        "scheme_name": "方案A - 痛点共鸣型",
        "visual_style": "极简莫兰迪",
        "headline": "告别干燥，喝饱的肌肤",
        "subheadline": "透明质酸钠深层渗透，28天见证蜕变",
        "body_copy": ["深层补水", "锁水保湿", "温和不刺激"],
        "cta": "立即体验",
        "scene_description": "极简白色背景，产品居中",
        "layout_description": "标题居上，产品居中，文案居下",
    })


@patch("content_generator._build_client")
def test_generate_poster_content_returns_scheme(mock_build):
    mock_client = MagicMock()
    mock_build.return_value = mock_client

    # Stage 1 mock: scheme JSON
    stage1_msg = MagicMock()
    stage1_msg.content = _mock_scheme_response()
    stage1_choice = MagicMock()
    stage1_choice.message = stage1_msg
    stage1_resp = MagicMock()
    stage1_resp.choices = [stage1_choice]

    # Stage 2 mock: image prompt in code block
    stage2_msg = MagicMock()
    stage2_msg.content = "```\nGenerate a minimalist poster with product...\n```"
    stage2_choice = MagicMock()
    stage2_choice.message = stage2_msg
    stage2_resp = MagicMock()
    stage2_resp.choices = [stage2_choice]

    mock_client.chat.completions.create.side_effect = [stage1_resp, stage2_resp]

    scheme = generate_poster_content(_make_record())

    assert isinstance(scheme, PosterScheme)
    assert scheme.headline == "告别干燥，喝饱的肌肤"
    assert "minimalist poster" in scheme.image_prompt
    assert mock_client.chat.completions.create.call_count == 2


@patch("content_generator._build_client")
def test_generate_poster_content_invalid_json_raises(mock_build):
    mock_client = MagicMock()
    mock_build.return_value = mock_client

    bad_msg = MagicMock()
    bad_msg.content = "这不是有效的JSON输出"
    bad_choice = MagicMock()
    bad_choice.message = bad_msg
    bad_resp = MagicMock()
    bad_resp.choices = [bad_choice]
    mock_client.chat.completions.create.return_value = bad_resp

    with pytest.raises(ValueError, match="Stage 1 JSON parse error"):
        generate_poster_content(_make_record())
