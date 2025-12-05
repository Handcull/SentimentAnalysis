from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
from .database import get_db
from .models import Feedback, Product
from .schemas import SentimentOverview, ProductSentiment
from typing import List, Optional
from datetime import date
from app.schemas import FeedbackJoined, ProductSentiment, TrendPoint, TrendSeries

router = APIRouter(prefix="/sentiment", tags=["Sentiment"])

# helpers for counts
POS = func.sum(case((Feedback.sentiment_label == "positive", 1), else_=0)).label("positive")
NEU = func.sum(case((Feedback.sentiment_label == "neutral", 1), else_=0)).label("neutral")
NEG = func.sum(case((Feedback.sentiment_label == "negative", 1), else_=0)).label("negative")
TOT = func.count(Feedback.id).label("total")

@router.get("/overview", response_model=SentimentOverview)
def sentiment_overview(db: Session = Depends(get_db)):
    row = db.query(POS, NEU, NEG, TOT).one()
    pos = int(row.positive or 0)
    neu = int(row.neutral or 0)
    neg = int(row.negative or 0)
    tot = int(row.total or 0)
    return {"positive": pos, "neutral": neu, "negative": neg, "total": tot}

@router.get("/by-product", response_model=List[ProductSentiment])
def sentiment_by_product(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Search product name/address/city"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("positive_pct", description="positive_pct|reviews_count|avg_rating"),
):
    # aggregate per product
    sub = (
        db.query(
            Feedback.product_id.label("pid"),
            func.sum(case((Feedback.sentiment_label == "positive", 1), else_=0)).label("positive"),
            func.sum(case((Feedback.sentiment_label == "neutral", 1), else_=0)).label("neutral"),
            func.sum(case((Feedback.sentiment_label == "negative", 1), else_=0)).label("negative"),
            func.count(Feedback.id).label("total"),
            func.avg(Feedback.rating).label("avg_rating"),
        )
        .group_by(Feedback.product_id)
        .subquery()
    )

    # expression for positive percent (use coalesce/nullif to avoid div-by-zero and NULL sort issues)
    positive_pct_expr = (
        (func.coalesce(sub.c.positive, 0) / func.nullif(sub.c.total, 0) * 100.0)
    )

    qset = (
        db.query(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            Product.city,
            Product.country,
            sub.c.total.label("reviews_count"),
            sub.c.positive,
            sub.c.neutral,
            sub.c.negative,
            positive_pct_expr.label("positive_pct"),
            sub.c.avg_rating,
        )
        .join(sub, sub.c.pid == Product.id)
    )

    if q:
        like = f"%{q}%"
        qset = qset.filter(
            or_(
                Product.name.ilike(like),
                Product.address.ilike(like),
                Product.city.ilike(like),
            )
        )

    # map sort key -> real SQLAlchemy expression
    sort_map = {
        "positive_pct": positive_pct_expr,
        "reviews_count": sub.c.total,
        "avg_rating": sub.c.avg_rating,
    }
    sort_expr = sort_map.get(sort, positive_pct_expr)

    # MySQL doesn’t support NULLS LAST; use COALESCE to make sorting stable
    qset = qset.order_by(func.coalesce(sort_expr, 0).desc())

    rows = qset.offset(offset).limit(limit).all()

    return [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "city": r.city,
            "country": r.country,
            "reviews_count": int(r.reviews_count or 0),
            "positive": int(r.positive or 0),
            "neutral": int(r.neutral or 0),
            "negative": int(r.negative or 0),
            "positive_pct": float(r.positive_pct or 0.0),
            "avg_rating": float(r.avg_rating) if r.avg_rating is not None else None,
        }
        for r in rows
    ]

@router.get("/product/{product_id}", response_model=ProductSentiment)
def sentiment_for_product(product_id: int, db: Session = Depends(get_db)):
    sub = (
        db.query(
            POS, NEU, NEG, TOT, func.avg(Feedback.rating).label("avg_rating")
        )
        .filter(Feedback.product_id == product_id)
        .one()
    )
    prod = db.query(Product).get(product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    pos = int(sub.positive or 0)
    neu = int(sub.neutral or 0)
    neg = int(sub.negative or 0)
    tot = int(sub.total or 0)
    pct = (pos / tot * 100.0) if tot else 0.0

    return {
        "product_id": prod.id,
        "product_name": prod.name,
        "city": prod.city,
        "country": prod.country,
        "reviews_count": tot,
        "positive": pos,
        "neutral": neu,
        "negative": neg,
        "positive_pct": pct,
        "avg_rating": float(sub.avg_rating) if sub.avg_rating is not None else None,
    }

def _trend_query(
    db: Session,
    product_id: Optional[int] = None,
    start: Optional[str] = None,   # "YYYY-MM" or full date "YYYY-MM-DD"
    end: Optional[str] = None,     # same format
):
    # MySQL monthly bucket: "YYYY-MM"
    period_expr = func.date_format(Feedback.review_date, "%Y-%m").label("period")

    q = (
        db.query(
            period_expr,
            func.sum(case((Feedback.sentiment_label == "positive", 1), else_=0)).label("positive"),
            func.sum(case((Feedback.sentiment_label == "neutral", 1), else_=0)).label("neutral"),
            func.sum(case((Feedback.sentiment_label == "negative", 1), else_=0)).label("negative"),
            func.count(Feedback.id).label("total"),
        )
        .filter(Feedback.review_date.isnot(None))
    )

    if product_id is not None:
        q = q.filter(Feedback.product_id == product_id)

    # Optional time window (works with "YYYY-MM" or "YYYY-MM-DD")
    if start:
        q = q.filter(Feedback.review_date >= start + ("-01" if len(start) == 7 else ""))
    if end:
        # add a generous upper bound
        q = q.filter(Feedback.review_date < (end + "-32" if len(end) == 7 else end))

    q = q.group_by(period_expr).order_by(period_expr)
    rows = q.all()

    return [
        {
            "period": r.period or "",
            "positive": int(r.positive or 0),
            "neutral": int(r.neutral or 0),
            "negative": int(r.negative or 0),
            "total": int(r.total or 0),
        }
        for r in rows
    ]


@router.get("/trend/overall", response_model=List[TrendPoint])
def sentiment_trend_overall(
    db: Session = Depends(get_db),
    start: Optional[str] = Query(None, description='Start month/date, e.g. "2015-01-01"'),
    end: Optional[str] = Query(None, description='End month/date, e.g. "2016-12-31"'),
):
    return _trend_query(db, None, start, end)


@router.get("/trend/product/{product_id}", response_model=List[TrendPoint])
def sentiment_trend_for_product(
    product_id: int,
    db: Session = Depends(get_db),
    start: Optional[str] = Query(None, description='Start month/date, e.g. "2015-01-01"'),
    end: Optional[str] = Query(None, description='End month/date, e.g. "2016-12-01"'),
):
    return _trend_query(db, product_id, start, end)


