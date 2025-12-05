from datetime import date, datetime
from typing import List, Dict, Any, Optional
from collections import Counter
import re
import io

import matplotlib.pyplot as plt
import pandas as pd
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from scipy.stats import pearsonr
import numpy as np

from app.database import get_db
from app.models import Review

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)

# ============================================================
# HELPER: Hitung huruf saja (tanpa spasi, angka, simbol, emoji)
# ============================================================

def count_letters(text: str) -> int:
    """Hitung jumlah huruf unicode dalam text."""
    if not text:
        return 0
    letters = re.findall(r"[^\W\d_]", text, flags=re.UNICODE)
    return len(letters)


# ============================================================
# HELPER: Tokenizing + Stopwords
# ============================================================

WORD_PATTERN = re.compile(r"\b\w+\b", flags=re.UNICODE)

STOPWORDS = {
    # English function words
    "the", "and", "or", "is", "are", "am", "was", "were",
    "be", "been", "being",
    "of", "to", "in", "on", "for", "with", "at", "by", "from",
    "this", "that", "these", "those",
    "a", "an", "it", "its", "as", "so", "if", "but",
    "very", "really", "just", "also", "too",

    # pronouns
    "i", "we", "you", "he", "she", "they", "it",
    "me", "us", "him", "her", "them",
    "my", "our", "your", "his", "their",

    # common hotel words
    "hotel", "room", "rooms", "place", "stay", "stayed",
    "location", "area", "night", "nights", "day", "days",

    # Indonesian
    "dan", "yang", "di", "ke", "dari", "itu", "ini", "untuk", "dengan",
    "kami", "kita", "saya", "aku", "dia", "mereka",
    "pada", "ada", "tidak", "bukan",
}

def extract_clean_words(text: str) -> List[str]:
    """
    Ambil kata-kata yang:
    - lowercase
    - mengandung huruf
    - bukan stopwords
    - panjang > 2
    """
    if not text:
        return []

    text = text.lower()
    tokens = WORD_PATTERN.findall(text)

    words: List[str] = []
    for t in tokens:
        # harus mengandung huruf
        if not re.search(r"[^\W\d_]", t, flags=re.UNICODE):
            continue
        # buang kata terlalu pendek
        if len(t) <= 2:
            continue
        # buang stopwords
        if t in STOPWORDS:
            continue
        words.append(t)
    return words


# ============================================================
# LEXICON SEDERHANA (bukan manual dari user, tapi daftar umum)
# ============================================================

POSITIVE_WORDS = {
    "excellent", "great", "good", "amazing", "clean", "friendly",
    "comfortable", "wonderful", "perfect", "nice", "helpful",
    "recommend", "love", "best", "enjoy", "spacious", "lovely",
    "fantastic", "awesome"
}

NEGATIVE_WORDS = {
    "bad", "terrible", "awful", "dirty", "rude", "worst", "broken",
    "poor", "noisy", "disappointed", "uncomfortable", "hate",
    "slow", "problem", "issue", "smell", "smelly", "horrible",
    "disgusting"
}


# ============================================================
# ENDPOINT 1 — WORD FREQUENCY (positif & negatif)
# ============================================================

@router.get("/word-frequency")
def word_frequency(
    db: Session = Depends(get_db),

    start_date: Optional[datetime] = Query(
        None,
        description="Tanggal mulai (format: YYYY-MM-DD atau YYYY-MM-DDTHH:MM:SS). Contoh: 2015-01-01"
    ),

    end_date: Optional[datetime] = Query(
        None,
        description="Tanggal akhir (format: YYYY-MM-DD atau YYYY-MM-DDTHH:MM:SS). Contoh: 2015-12-31"
    ),

    top_k: int = Query(
        20,
        ge=1,
        le=100,
        description="Jumlah kata teratas yang ingin ditampilkan. Contoh: 20"
    ),
):
    """
    Hitung kata POSITIF & NEGATIF yang paling sering muncul di review,
    berdasarkan lexicon kata umum (tanpa input manual).
    """

    q = db.query(Review).filter(Review.text.isnot(None))

    if start_date:
        q = q.filter(Review.review_date >= start_date)
    if end_date:
        q = q.filter(Review.review_date <= end_date)

    reviews = q.all()

    pos_counter = Counter()
    neg_counter = Counter()
    pos_hits = set()
    neg_hits = set()

    for r in reviews:
        words = extract_clean_words(r.text or "")
        if not words:
            continue

        found_pos = False
        found_neg = False

        for w in words:
            if w in POSITIVE_WORDS:
                pos_counter.update([w])
                found_pos = True
            if w in NEGATIVE_WORDS:
                neg_counter.update([w])
                found_neg = True

        if found_pos:
            pos_hits.add(r.id)
        if found_neg:
            neg_hits.add(r.id)

    return {
        "total_reviews_scanned": len(reviews),
        "reviews_with_positive_words": len(pos_hits),
        "reviews_with_negative_words": len(neg_hits),
        "top_k": top_k,
        "positive_top_words": [
            {"word": w, "count": c} for w, c in pos_counter.most_common(top_k)
        ],
        "negative_top_words": [
            {"word": w, "count": c} for w, c in neg_counter.most_common(top_k)
        ],
    }


# ============================================================
# ENDPOINT 2 — SENTIMENT TREND (plot PNG)
# ============================================================

@router.get("/sentiment-trend")
def sentiment_trend(
    db: Session = Depends(get_db),

    start_date: Optional[date] = Query(
        None,
        description="Tanggal mulai (format: YYYY-MM-DD). Contoh: 2015-01-01"
    ),

    end_date: Optional[date] = Query(
        None,
        description="Tanggal akhir (format: YYYY-MM-DD). Contoh: 2015-12-31"
    ),

    interval: str = Query(
        "monthly",
        description="Interval waktu: 'daily', 'weekly', atau 'monthly' (default)."
    ),
):
    """
    Plot perubahan sentiment rata-rata (polarity) dari waktu ke waktu.
    Mengembalikan gambar PNG.
    """

    q = db.query(Review).filter(
        Review.polarity.isnot(None),
        Review.review_date.isnot(None),
    )

    if start_date:
        q = q.filter(Review.review_date >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        q = q.filter(Review.review_date <= datetime.combine(end_date, datetime.max.time()))

    reviews = q.all()
    if not reviews:
        return {"error": "Tidak ada data pada rentang ini."}

    df = pd.DataFrame({
        "date": [r.review_date for r in reviews],
        "polarity": [r.polarity for r in reviews],
    })

    if interval == "daily":
        grouped = df.groupby(df["date"].dt.date).mean(numeric_only=True)
    elif interval == "weekly":
        grouped = df.groupby(df["date"].dt.to_period("W")).mean(numeric_only=True)
    else:  # monthly default
        grouped = df.groupby(df["date"].dt.to_period("M")).mean(numeric_only=True)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(grouped.index.astype(str), grouped["polarity"], marker="o")
    ax.set_title("Sentiment Trend Over Time")
    ax.set_xlabel("Time")
    ax.set_ylabel("Average Polarity")
    ax.grid(True)
    plt.xticks(rotation=45)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")


# ============================================================
# ENDPOINT 3A — RATING vs LENGTH (JSON statistik)
# ============================================================

@router.get("/rating-length-correlation")
def rating_length_correlation(
    db: Session = Depends(get_db),

    start_date: Optional[date] = Query(
        None,
        description="Tanggal mulai (format: YYYY-MM-DD). Contoh: 2015-01-01"
    ),

    end_date: Optional[date] = Query(
        None,
        description="Tanggal akhir (format: YYYY-MM-DD). Contoh: 2016-01-01"
    ),
):
    """
    Analisis hubungan rating vs panjang review (jumlah huruf).
    Mengembalikan:
      - rata-rata panjang per rating
      - nilai korelasi Pearson
      - p-value
    """

    q = db.query(Review).filter(
        Review.rating.isnot(None),
        Review.text.isnot(None),
        Review.text != "",
    )

    if start_date:
        q = q.filter(Review.review_date >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        q = q.filter(Review.review_date <= datetime.combine(end_date, datetime.max.time()))

    reviews = q.all()
    if not reviews:
        return {"error": "Tidak ada review dalam rentang ini."}

    records = [(r.rating, count_letters(r.text)) for r in reviews]

    ratings = np.array([r for r, L in records])
    lengths = np.array([L for r, L in records])

    pearson_r, p_value = pearsonr(ratings, lengths)

    avg_length_per_rating: Dict[int, Optional[float]] = {}
    for rating in range(1, 6):
        subset = [L for r, L in records if r == rating]
        avg_length_per_rating[rating] = float(np.mean(subset)) if subset else None

    return {
        "avg_length_per_rating": avg_length_per_rating,
        "pearson_r": float(pearson_r),
        "p_value": float(p_value),
    }


# ============================================================
# ENDPOINT 3B — RATING vs LENGTH (scatter plot PNG)
# ============================================================

@router.get("/rating-length-correlation/plot")
def rating_length_correlation_plot(
    db: Session = Depends(get_db),

    start_date: Optional[date] = Query(
        None,
        description="Tanggal mulai (format: YYYY-MM-DD). Contoh: 2015-01-01"
    ),

    end_date: Optional[date] = Query(
        None,
        description="Tanggal akhir (format: YYYY-MM-DD). Contoh: 2016-01-01"
    ),
):
    """
    Versi visual dari rating-length-correlation:
    Mengembalikan scatter plot (PNG) rating vs panjang review (letters only).
    """

    q = db.query(Review).filter(
        Review.rating.isnot(None),
        Review.text.isnot(None),
        Review.text != "",
    )

    if start_date:
        q = q.filter(Review.review_date >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        q = q.filter(Review.review_date <= datetime.combine(end_date, datetime.max.time()))

    reviews = q.all()
    if not reviews:
        return {"error": "Tidak ada review dalam rentang ini."}

    records = [(r.rating, count_letters(r.text)) for r in reviews]
    ratings = np.array([r for r, L in records])
    lengths = np.array([L for r, L in records])

    pearson_r, _ = pearsonr(ratings, lengths)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(lengths, ratings, alpha=0.6)
    ax.set_title(f"Rating vs Review Length (letters only)\nPearson r = {pearson_r:.4f}")
    ax.set_xlabel("Review Length (letters only)")
    ax.set_ylabel("Rating (1–5)")
    ax.grid(True)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")
