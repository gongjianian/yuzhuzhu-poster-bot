from __future__ import annotations

from pydantic import BaseModel, Field


class ProductRecord(BaseModel):
    record_id: str
    product_name: str
    ingredients: str = ""
    benefits: str = ""
    xiaohongshu_topics: str = ""
    category: str = "未分类"
    visual_style: str = "极简扁平"
    brand_colors: str = "#FFFFFF"
    asset_filename: str = ""
    status: str = "PENDING"
    idempotency_key: str = ""


class PosterScheme(BaseModel):
    scheme_name: str
    visual_style: str
    headline: str
    subheadline: str
    body_copy: list[str]
    cta: str
    image_prompt: str
    aspect_ratio: str = "3:4"


class QCResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    confidence: float = 1.0
