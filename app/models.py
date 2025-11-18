from sqlalchemy import Column, Integer, String, Float
from .database import Base
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base



class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    categories = Column(String(100))
    address = Column(String(255))
    city = Column(String(100))
    province = Column(String(100))
    country = Column(String(50))
    postalCode = Column(String(20))
    latitude = Column(Float)
    longitude = Column(Float)

    # Relation to feedback table
    feedbacks = relationship("Feedback", back_populates="product")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), index=True)          # we can enforce unique later if needed
    user_city = Column(String(100))
    user_province = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relation to feedback table
    feedbacks = relationship("Feedback", back_populates="user")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    rating = Column(Integer)                 # 1–5 from the CSV
    title = Column(String(255))
    text = Column(Text)
    review_date = Column(DateTime)          # from reviews.date
    sentiment_label = Column(String(20))    # "positive"/"neutral"/"negative" (computed later)
    text_length = Column(Integer)           # for correlation analysis
    created_at = Column(DateTime, default=datetime.utcnow)
    
    #Relationship
    user = relationship("User", back_populates="feedbacks")
    product = relationship("Product", back_populates="feedbacks")
