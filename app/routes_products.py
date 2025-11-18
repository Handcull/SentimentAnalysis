from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from .database import get_db
from .models import Product
from .schemas import ProductOut

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/", response_model=List[ProductOut])
def list_products(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Search in name/address/city"),
    city: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    qset = db.query(Product)
    if q:
        like = f"%{q}%"
        qset = qset.filter(
            or_(
                Product.name.ilike(like),
                Product.address.ilike(like),
                Product.city.ilike(like),
                Product.categories.ilike(like),
            )
        )
    if city:
        qset = qset.filter(Product.city == city)
    if country:
        qset = qset.filter(Product.country == country)

    return qset.order_by(Product.id).offset(offset).limit(limit).all()
