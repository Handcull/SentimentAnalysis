from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.database import SessionLocal, get_db
from app.models import Review, User
from app.utils.sentiment import analyze_sentiment


router = APIRouter(
    prefix="/reviews",
    tags=["Reviews"],
)


# =========================
# Pydantic Schemas
# =========================
class ReviewBase(BaseModel):
    product_id: int = 0
    user_id: int
    rating: Optional[int] = None
    title: Optional[str] = None
    text: Optional[str] = None
    review_date: Optional[datetime] = None


class ReviewCreate(ReviewBase):
    pass


class ReviewOut(ReviewBase):
    id: int
    sentiment_label: Optional[str] = None
    polarity: Optional[float] = None
    subjectivity: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True  # pengganti orm_mode di Pydantic v2


# =========================
# Endpoints
# =========================

@router.get("/", response_model=List[ReviewOut])
def list_reviews(
    db: Session = Depends(get_db),
    product_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    rating_min: Optional[int] = Query(None, ge=0, le=5),
    rating_max: Optional[int] = Query(None, ge=0, le=5),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Ambil daftar review.
    Bisa difilter dengan:
    - product_id
    - user_id
    - rating_min, rating_max
    """
    q = db.query(Review)
    filters = []

    if product_id is not None:
        filters.append(Review.product_id == product_id)
    if user_id is not None:
        filters.append(Review.user_id == user_id)
    if rating_min is not None:
        filters.append(Review.rating >= rating_min)
    if rating_max is not None:
        filters.append(Review.rating <= rating_max)

    if filters:
        q = q.filter(and_(*filters))

    reviews = (
        q.order_by(Review.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return reviews


@router.post("/", response_model=ReviewOut)
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)):
    """
    Tambah review baru + langsung analisa sentiment (multilingual 1–5 bintang).
    """

    # Cek user
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User dengan id itu tidak ditemukan.")

    review_date = payload.review_date or datetime.utcnow()

    # === ANALISIS SENTIMENT (pakai utils/sentiment.py) ===
    result = analyze_sentiment(payload.text)
    # result: {"stars", "label", "score", "is_sarcastic"}

    sentiment_label = result["label"]          # very positive / negative / neutral
    polarity = result["score"]                # angka 0–1 dari model
    subjectivity = 1.0 if result["is_sarcastic"] else 0.0   # 1 = sarkas, 0 = biasa

    # === SIMPAN KE DB ===
    review = Review(
        product_id=payload.product_id,
        user_id=payload.user_id,
        rating=payload.rating,
        title=payload.title,
        text=payload.text,
        review_date=review_date,
        sentiment_label=sentiment_label,
        polarity=polarity,
        subjectivity=subjectivity,
    )

    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.delete("/{review_id}")
def delete_review(review_id: int, db: Session = Depends(get_db)):
    """
    Hapus satu review berdasarkan id.
    """
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review tidak ditemukan.")

    db.delete(review)
    db.commit()
    return {"message": f"Review {review_id} sudah dihapus."}

@router.get("/stats/summary")
def sentiment_summary(db: Session = Depends(get_db)):
    """
    Ringkasan statistik sentiment dari semua review.
    - total_reviews
    - avg_rating
    - avg_polarity (rata-rata score sentiment)
    - sentiment_counts (jumlah per label)
    - sarcasm_rate (persentase review yang terdeteksi sarkas)
    """
    # 1. Hitung total review
    total_reviews = db.query(func.count(Review.id)).scalar() or 0

    # 2. Rata-rata rating dan polarity (score sentiment)
    avg_rating = db.query(func.avg(Review.rating)).scalar()
    avg_polarity = db.query(func.avg(Review.polarity)).scalar()

    # 3. Hitung jumlah tiap sentiment_label
    rows = (
        db.query(Review.sentiment_label, func.count(Review.id))
        .group_by(Review.sentiment_label)
        .all()
    )
    sentiment_counts = {label or "UNKNOWN": count for label, count in rows}

    # 4. Hitung persentase sarkas (kita simpan sarkas sebagai subjectivity = 1.0)
    sarcasm_count = (
        db.query(func.count(Review.id))
        .filter(Review.subjectivity == 1.0)
        .scalar()
        or 0
    )
    sarcasm_rate = (sarcasm_count / total_reviews) if total_reviews > 0 else 0.0

    return {
        "total_reviews": total_reviews,
        "avg_rating": float(avg_rating) if avg_rating is not None else None,
        "avg_polarity": float(avg_polarity) if avg_polarity is not None else None,
        "sentiment_counts": sentiment_counts,
        "sarcasm_count": sarcasm_count,
        "sarcasm_rate": sarcasm_rate,
    }
