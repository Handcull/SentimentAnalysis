from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from typing import List

class ConfigORM(BaseModel):
    class Config:
        orm_mode = True

class ProductOut(ConfigORM):
    id: int
    name: Optional[str]
    categories: Optional[str]
    address: Optional[str]
    city: Optional[str]
    province: Optional[str]
    country: Optional[str]
    postalCode: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]

class UserOut(ConfigORM):
    id: int
    username: Optional[str]
    user_city: Optional[str]
    user_province: Optional[str]
    created_at: datetime

class FeedbackOut(ConfigORM):
    id: int
    product_id: int
    user_id: Optional[int]
    rating: Optional[int]
    title: Optional[str]
    text: Optional[str]
    review_date: Optional[datetime]
    sentiment_label: Optional[str]
    text_length: int
    created_at: datetime

# Expanded feedback with joined fields (product name + username)
class FeedbackJoined(ConfigORM):
    id: int
    product_id: int
    product_name: Optional[str]
    user_id: Optional[int]
    username: Optional[str]
    rating: Optional[int]
    title: Optional[str]
    text: Optional[str]
    review_date: Optional[datetime]
    sentiment_label: Optional[str]
    text_length: int
    created_at: datetime

class SentimentOverview(ConfigORM):
    positive: int
    neutral: int
    negative: int
    total: int

class ProductSentiment(ConfigORM):
    product_id: int
    product_name: Optional[str]
    city: Optional[str]
    country: Optional[str]
    reviews_count: int
    positive: int
    neutral: int
    negative: int
    positive_pct: float
    avg_rating: Optional[float]


class TrendPoint(ConfigORM):
    period: str          # e.g. "2016-05"
    positive: int
    neutral: int
    negative: int
    total: int

class TrendSeries(ConfigORM):
    series: List[TrendPoint]

