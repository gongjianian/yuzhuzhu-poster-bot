import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from models import ProductRecord, CategoryPosterTask, PosterScheme


def _make_task():
    p = ProductRecord(
        record_id="r1", product_name="鸡内金泡浴", benefits="消食化积",
        ingredients="鸡内金", product_line="五行泡浴", asset_filename="jineijin.jpg",
    )
    return CategoryPosterTask(
        category_id="cat_pw_jstl",
        level1_category_id="cat_piwei",
        category_name="积食停滞类",
        product_line="五行泡浴",
        products=[p],
    )


def _make_scheme():
    return PosterScheme(
        scheme_name="test", visual_style="极简", headline="标题",
        subheadline="副标题", body_copy=["卖点1"], cta="立即查看",
        image_prompt="A poster...", aspect_ratio="3:4",
    )


@pytest.mark.asyncio
@patch("category_pipeline.upload_image", return_value="cloud://env/materials/test.jpg")
@patch("category_pipeline.register_material", return_value="mat_001")
@patch("category_pipeline.generate_poster_image", return_value=b"FAKEPNG")
@patch("category_pipeline.process_product_image", return_value="base64img")
@patch("category_pipeline.generate_category_poster_content")
async def test_process_category_task_success(
    mock_content, mock_asset, mock_image, mock_register, mock_upload
):
    from category_pipeline import process_category_task
    mock_content.return_value = _make_scheme()

    result = await process_category_task(_make_task())

    assert result["status"] == "DONE"
    assert result["cloud_file_id"] == "cloud://env/materials/test.jpg"
    assert result["material_id"] == "mat_001"
    mock_register.assert_called_once()


@pytest.mark.asyncio
@patch("category_pipeline.process_product_image", side_effect=FileNotFoundError("no asset"))
async def test_process_category_task_missing_asset(mock_asset):
    from category_pipeline import process_category_task
    result = await process_category_task(_make_task())
    assert result["status"] == "FAILED"
    assert "asset" in result["error_msg"].lower()


@pytest.mark.asyncio
@patch("category_pipeline.fetch_all_records")
@patch("category_pipeline.match_products_to_symptom")
async def test_run_daily_category_pipeline_iterates_all_categories(
    mock_match, mock_fetch
):
    from category_pipeline import run_daily_category_pipeline
    from symptom_categories import ALL_SYMPTOM_CATEGORIES

    mock_fetch.return_value = []
    mock_match.return_value = []

    results = await run_daily_category_pipeline()

    assert mock_match.call_count == len(ALL_SYMPTOM_CATEGORIES)
    assert isinstance(results, list)
