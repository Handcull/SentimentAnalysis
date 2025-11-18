import math
import pandas as pd
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Product, User, Feedback

# Path to your dataset
CSV_PATH = "data/7282_1.csv"

# --- Utility functions ---
def to_none(x):
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    if isinstance(x, str) and x.strip().lower() in {"nan", "none", ""}:
        return None
    return x

def safe_len(s: str | None) -> int:
    return len(s) if isinstance(s, str) else 0


# --- Main importer ---
def main():
    use_cols = [
        "name", "address", "city", "province", "country",
        "reviews.date", "reviews.rating", "reviews.text", "reviews.title",
        "reviews.userCity", "reviews.username", "reviews.userProvince",
    ]

    # Step 1 — Read CSV
    df = pd.read_csv(
        CSV_PATH,
        usecols=use_cols,
        parse_dates=["reviews.date"],
        infer_datetime_format=True,
        dayfirst=False,
    )

    print("✅ CSV loaded successfully")
    print("📊 Shape:", df.shape)
    print("📋 Columns:", df.columns.tolist())
    print(df.head(3))

    # Step 2 — Prepare data
    for c in use_cols:
        if c == "reviews.rating":
            continue
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip()
            df[c] = df[c].replace({"nan": None, "None": None, "": None})

    def to_int(x):
        try:
            if pd.isna(x):
                return None
            return int(float(x))
        except Exception:
            return None

    df["reviews.rating"] = df["reviews.rating"].apply(to_int)

    # Step 3 — Database session
    db: Session = SessionLocal()
    created_users = 0
    created_feedback = 0

    try:
        for i, row in enumerate(df.to_dict(orient="records"), start=1):
            # helper shortcut
            def col(name):
                return row.get(name) or row.get(name.replace(".", "_"))

            # find product
            prod = (
                db.query(Product)
                .filter(Product.name == col("name"), Product.address == col("address"))
                .first()
            )
            if prod is None:
                prod = db.query(Product).filter(Product.name == col("name")).first()
            if prod is None:
                continue

            # upsert user
            username = to_none(col("reviews.username"))
            user = None
            if username:
                user = db.query(User).filter(User.username == username).first()
                if user is None:
                    user = User(
                        username=username,
                        user_city=to_none(col("reviews.userCity")),
                        user_province=to_none(col("reviews.userProvince")),
                    )
                    db.add(user)
                    created_users += 1
                    db.flush()  # fetch id

            # feedback
            rev_date = col("reviews.date")
            if hasattr(rev_date, "to_pydatetime"):
                rev_date = rev_date.to_pydatetime()

            fb = Feedback(
                product_id=prod.id,
                user_id=(user.id if user else None),
                rating=to_none(col("reviews.rating")),
                title=to_none(col("reviews.title")),
                text=to_none(col("reviews.text")),
                review_date=rev_date,
                sentiment_label=None,
                text_length=safe_len(to_none(col("reviews.text"))),
            )
            db.add(fb)
            created_feedback += 1

            if i % 500 == 0:
                db.commit()
                print(f"...processed {i} rows")

        db.commit()
        print(f"✅ Imported users: {created_users}")
        print(f"✅ Imported feedback: {created_feedback}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
