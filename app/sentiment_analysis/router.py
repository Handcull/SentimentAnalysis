from fastapi import APIRouter
from pydantic import BaseModel

from app.utils.sentiment import analyze_sentiment


router = APIRouter(
    prefix="/sentiment",
    tags=["sentiment"],
)


class SentimentRequest(BaseModel):
    text: str


class SentimentResponse(BaseModel):
    stars: int | None
    label: str
    score: float

class SentimentResponse(BaseModel):
    stars: int | None
    label: str
    score: float
    is_sarcastic: bool


@router.post("/analyze", response_model=SentimentResponse)
def analyze_text_sentiment(payload: SentimentRequest):
    """
    Terima teks dari user -> kembalikan hasil analisa sentiment.
    """
    result = analyze_sentiment(payload.text)

    return SentimentResponse(
        stars=result["stars"],
        label=result["label"],
        score=result["score"],
        is_sarcastic=result["is_sarcastic"],
    )
