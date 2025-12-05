from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
from .schemas import UserOut

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Search by username"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    qset = db.query(User)
    if q:
        qset = qset.filter(User.username.ilike(f"%{q}%"))
    return qset.order_by(User.id).offset(offset).limit(limit).all()
