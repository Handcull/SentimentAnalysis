from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Review

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


# =========================
# Pydantic Schemas
# =========================
class UserBase(BaseModel):
    username: str
    user_city: Optional[str] = None
    user_province: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        # Pydantic v2: pengganti orm_mode = True
        from_attributes = True


# =========================
# Endpoints
# =========================

@router.get("/", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Cari berdasarkan username"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Ambil daftar user.
    - Bisa pakai parameter q untuk search username (LIKE).
    - Pakai limit & offset untuk pagination.
    """
    query = db.query(User)

    if q:
        pattern = f"%{q}%"
        query = query.filter(User.username.ilike(pattern))

    users = (
        query.order_by(User.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return users


@router.get("/count")
def count_users(db: Session = Depends(get_db)):
    """
    Kembalikan total user di database.
    """
    total = db.query(User).count()
    return {"total_users": total}


@router.post("/", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    """
    Tambah user baru.
    - Kalau username sudah ada, lempar error 400.
    """
    existing = (
        db.query(User)
        .filter(User.username == payload.username)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Username sudah terpakai.",
        )

    user = User(
        username=payload.username,
        user_city=payload.user_city,
        user_province=payload.user_province,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """
    Hapus user berdasarkan id.
    - Sekaligus hapus semua reviews yang dimiliki user tersebut.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")

    # hapus review milik user ini
    db.query(Review).filter(Review.user_id == user_id).delete()

    # hapus user
    db.delete(user)
    db.commit()

    return {"message": f"User {user_id} dan semua review-nya sudah dihapus."}
