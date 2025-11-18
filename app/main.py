from fastapi import FastAPI
from app.routes_products import router as products_router
from app.routes_users import router as users_router
from app.routes_feedback import router as feedback_router
from app.routes_feedback_sentiment import router as sentiment_router
from app.routes_feedback_summary import router as summary_router

app = FastAPI(title="Sentiment System", version="0.1.0")

@app.get("/")
def root():
    return {"message": "Sentiment System API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

# NEW: include routers
app.include_router(products_router)
app.include_router(users_router)
app.include_router(feedback_router)
app.include_router(sentiment_router)
app.include_router(summary_router) 

