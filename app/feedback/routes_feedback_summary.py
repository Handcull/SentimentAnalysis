from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Feedback, Product
from sqlalchemy import func, case


router = APIRouter(prefix="/summary", tags=["Summary"])

@router.get("/overall")
def sentiment_overall_summary(db: Session = Depends(get_db)):
    total = db.query(func.count(Feedback.id)).scalar()
    grouped = (
        db.query(Feedback.sentiment_label, func.count(Feedback.id))
        .group_by(Feedback.sentiment_label)
        .all()
    )
    data = {label or "unknown": count for label, count in grouped}
    for lbl in ["positive", "neutral", "negative"]:
        data.setdefault(lbl, 0)
    return {
        "total_feedback": total,
        "positive_pct": round(data["positive"] / total * 100, 2),
        "neutral_pct": round(data["neutral"] / total * 100, 2),
        "negative_pct": round(data["negative"] / total * 100, 2),
        "counts": data,
    }

@router.get("/by-product")
def sentiment_summary_by_product(
    db: Session = Depends(get_db),
    sort_by: str = Query("reviews", description="Sort by: reviews | rating | positive | negative"),
    limit: int = Query(20, ge=1, le=100, description="Number of top products to return")
):
    q = (
        db.query(
            Product.id,
            Product.name,
            func.count(Feedback.id).label("review_count"),
            func.avg(Feedback.rating).label("avg_rating"),
            func.sum(case((Feedback.sentiment_label == "positive", 1), else_=0)).label("positive"),
            func.sum(case((Feedback.sentiment_label == "neutral", 1), else_=0)).label("neutral"),
            func.sum(case((Feedback.sentiment_label == "negative", 1), else_=0)).label("negative"),
        )
        .join(Feedback, Feedback.product_id == Product.id)
        .group_by(Product.id)
    )

    # Dynamic sorting
    sort_options = {
        "reviews": func.count(Feedback.id).desc(),
        "rating": func.avg(Feedback.rating).desc(),
        "positive": func.sum(case((Feedback.sentiment_label == "positive", 1), else_=0)).desc(),
        "negative": func.sum(case((Feedback.sentiment_label == "negative", 1), else_=0)).desc(),
    }
    q = q.order_by(sort_options.get(sort_by, sort_options["reviews"])).limit(limit)

    rows = q.all()
    return [
        {
            "product_id": pid,
            "name": name,
            "review_count": rc,
            "avg_rating": float(avg or 0),
            "positive": int(pos or 0),
            "neutral": int(neu or 0),
            "negative": int(neg or 0)
        }
        for pid, name, rc, avg, pos, neu, neg in rows
    ]
