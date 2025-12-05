from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Product

router = APIRouter(prefix="/products", tags=["Products"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", summary="List products with optional filters")
def list_products(
    q: Optional[str] = Query(None, description="Cari berdasarkan nama hotel"),
    city: Optional[str] = Query(None, description="Filter berdasarkan kota"),
    province: Optional[str] = Query(None, description="Filter berdasarkan provinsi"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Product)

    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))

    if city:
        query = query.filter(Product.city.ilike(f"%{city}%"))

    if province:
        query = query.filter(Product.province.ilike(f"%{province}%"))

    query = query.order_by(Product.id)

    products = query.offset(offset).limit(limit).all()

    return products
