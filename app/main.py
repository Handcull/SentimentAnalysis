from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.products.router import router as products_router
from app.users.router import router as users_router
from app.feedback.router import router as reviews_router
from app.sentiment_analysis import router as sentiment_router
from app.analytics.router import router as analytics_router



app = FastAPI(title="Sentiment System UAS", version="0.1.0")


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Sentiment System v2 API is running"}


@app.get("/db-test", include_in_schema=False)
def db_test(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"message": "Connected to MySQL!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# include router users
app.include_router(products_router)
app.include_router(users_router)
app.include_router(reviews_router)
app.include_router(sentiment_router)
app.include_router(analytics_router)


from fastapi.responses import StreamingResponse
import matplotlib.pyplot as plt
import io

@app.get("/plot.png")
def plot_png():
    # 1. Bikin figure Matplotlib
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3, 4], [10, 3, 7, 9])
    ax.set_title("Contoh Plot")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")

    # 2. Simpan ke buffer (bukan ke file)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)  # biar memory nggak bocor
    buf.seek(0)

    # 3. Kirim sebagai response gambar
    return StreamingResponse(buf, media_type="image/png")
