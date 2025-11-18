from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from .database import get_db
from .models import Feedback, Product, User
from .schemas import FeedbackOut, FeedbackJoined

router = APIRouter(prefix="/feedback", tags=["Feedback"])

@router.get("/", response_model=List[FeedbackJoined])
def list_feedback(
    db: Session = Depends(get_db),
    product_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    rating_min: Optional[int] = Query(None, ge=0, le=5),
    rating_max: Optional[int] = Query(None, ge=0, le=5),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    q = (
        db.query(
            Feedback.id,
            Feedback.product_id,
            Product.name.label("product_name"),
            Feedback.user_id,
            User.username,
            Feedback.rating,
            Feedback.title,
            Feedback.text,
            Feedback.review_date,
            Feedback.sentiment_label,
            Feedback.text_length,
            Feedback.created_at,
        )
        .join(Product, Feedback.product_id == Product.id)
        .join(User, Feedback.user_id == User.id, isouter=True)
    )

    filters = []
    if product_id is not None:
        filters.append(Feedback.product_id == product_id)
    if user_id is not None:
        filters.append(Feedback.user_id == user_id)
    if rating_min is not None:
        filters.append(Feedback.rating >= rating_min)
    if rating_max is not None:
        filters.append(Feedback.rating <= rating_max)

    if filters:
        q = q.filter(and_(*filters))

    q = q.order_by(Feedback.id).offset(offset).limit(limit)

    rows = q.all()
    # map to schema dicts
    return [
        {
            "id": r.id,
            "product_id": r.product_id,
            "product_name": r.product_name,
            "user_id": r.user_id,
            "username": r.username,
            "rating": r.rating,
            "title": r.title,
            "text": r.text,
            "review_date": r.review_date,
            "sentiment_label": r.sentiment_label,
            "text_length": r.text_length,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/raw", response_model=List[FeedbackOut])
def list_feedback_raw(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return (
        db.query(Feedback)
        .order_by(Feedback.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
