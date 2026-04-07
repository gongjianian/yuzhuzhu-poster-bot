import pytest
from pydantic import ValidationError

from models import PosterScheme, ProductRecord, QCResult


def test_product_record_valid() -> None:
    record = ProductRecord(record_id="rec_001", product_name="Test Product")

    assert record.record_id == "rec_001"
    assert record.product_name == "Test Product"
    assert record.status == "PENDING"
    assert record.cloud_file_id == ""


def test_product_record_missing_required() -> None:
    with pytest.raises(ValidationError):
        ProductRecord(record_id="rec_002")


def test_poster_scheme_valid() -> None:
    scheme = PosterScheme(
        scheme_name="minimal",
        visual_style="Minimal",
        headline="Headline",
        subheadline="Subheadline",
        body_copy=["Line 1", "Line 2"],
        cta="Try now",
        image_prompt="Create a clean product poster",
    )

    assert scheme.aspect_ratio == "3:4"
    assert scheme.body_copy == ["Line 1", "Line 2"]


def test_qc_result_valid() -> None:
    result = QCResult(passed=True)

    assert result.passed is True
    assert result.issues == []
    assert result.confidence == 1.0


def test_qc_result_failed() -> None:
    result = QCResult(
        passed=False,
        issues=["Logo distorted", "Text unreadable"],
        confidence=0.35,
    )

    assert result.passed is False
    assert result.issues == ["Logo distorted", "Text unreadable"]
    assert result.confidence == 0.35
