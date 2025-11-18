# app/sentiment_analyzer.py
from textblob import TextBlob
from app.database import SessionLocal
from app.models import Feedback
from datetime import datetime

def analyze_sentiment(text):
    """Return sentiment label: Positive / Negative / Neutral"""
    if not text or not text.strip():
        return "neutral"
    
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity  # value between -1 and 1

    if polarity > 0.1:
        return "positive"
    elif polarity < -0.1:
        return "negative"
    else:
        return "neutral"

def main():
    db = SessionLocal()
    feedbacks = db.query(Feedback).filter(Feedback.sentiment_label == None).all()

    total = len(feedbacks)
    print(f"🧠 Found {total} feedback entries without sentiment.")

    updated = 0
    for fb in feedbacks:
        fb.sentiment_label = analyze_sentiment(fb.text)
        fb.created_at = fb.created_at or datetime.utcnow()
        updated += 1
        if updated % 500 == 0:
            print(f"...processed {updated}/{total}")

    db.commit()
    print(f"✅ Done! Updated {updated} feedback rows.")
    db.close()

if __name__ == "__main__":
    main()
