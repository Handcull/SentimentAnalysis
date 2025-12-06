from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Review
from app.utils.sentiment import analyze_sentiment


BATCH_COMMIT = 500  # commit tiap 500 review biar gak berat


def main():
    db: Session = SessionLocal()

    # Ambil hanya review yang:
    # - text-nya tidak kosong
    # - belum punya sentiment_label (masih NULL)
    q = (
        db.query(Review)
        .filter(Review.text.isnot(None))
        .filter(Review.text != "")
        .filter(Review.sentiment_label.is_(None))
        .order_by(Review.id)
    )

    total = q.count()
    print(f"Total review yang akan dianalisa: {total}")

    processed = 0

    for review in q:
        # Jalankan sentiment analysis
        result = analyze_sentiment(review.text)

        review.sentiment_label = result["label"]
        review.polarity = result["score"]
        review.subjectivity = 1.0 if result["is_sarcastic"] else 0.0

        processed += 1

        # Commit per beberapa ratus baris
        if processed % BATCH_COMMIT == 0:
            db.commit()
            print(f"{processed} / {total} review sudah dianalisa...")

    # Commit sisa yang belum ke-commit
    db.commit()
    print(f"Selesai! Total {processed} review dianalisa.")

    db.close()


if __name__ == "__main__":
    main()
