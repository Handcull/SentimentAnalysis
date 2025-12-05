from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    city = Column(String(100))
    province = Column(String(100))
    country = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)

    # optional: hubungan ke Review
    reviews = relationship("Review", back_populates="product", lazy="selectin")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255))
    user_city = Column(String(255))
    user_province = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    # relasi ke reviews
    reviews = relationship("Review", back_populates="user")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    rating = Column(Integer)
    title = Column(Text)
    text = Column(Text)
    review_date = Column(DateTime)

    # kolom sentiment
    sentiment_label = Column(String(20))
    polarity = Column(Float)
    subjectivity = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)


    user = relationship("User", back_populates="reviews")

    product_id = Column(Integer, ForeignKey("products.id"), default=0)
    product = relationship("Product", back_populates="reviews")


