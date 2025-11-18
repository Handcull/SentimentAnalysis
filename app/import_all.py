import math
import pandas as pd
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Product, User, Feedback

CSV_PATH = "data/7282_1.csv"

def to_none(x):
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    if isinstance(x, str) and x.strip().lower() in {"nan", "none", ""}:
        return None
    return x

def to_int(x):
    try:
        if pd.isna(x):
            return None
        return int(float(x))
    except Exception:
        return None

def to_float_or_none(x):
    if x is None:
        return None
    # pandas NaN (float) → None
    if isinstance(x, float) and math.isnan(x):
        return None
    try:
        return float(x)
    except Exception:
        return None

def clean_postal(x):
    """
    Ensure postalCode is stored as a string:
    - NaN/None -> None
    - 02116 should stay '02116' (not 2116)
    - 12345.0 -> '12345'
    - otherwise str(x)
    """
    x = to_none(x)
    if x is None:
        return None
    # if pandas parsed as float
    if isinstance(x, float):
        if math.isnan(x):
            return None
        # 12345.0 -> '12345'
        if float(x).is_integer():
            return str(int(x))
        return str(x)
    # already string
    s = str(x).strip()
    return s if s else None

def main():
    use_cols = [
        # product columns
        "name","categories","address","city","province","country",
        "postalCode","latitude","longitude",
        # review columns
        "reviews.date","reviews.rating","reviews.text","reviews.title",
        "reviews.userCity","reviews.username","reviews.userProvince",
    ]

    df = pd.read_csv(
        CSV_PATH,
        usecols=use_cols,
        parse_dates=["reviews.date"],
    )

    print("✅ CSV loaded:", df.shape)

    # Clean string-like columns (leave numeric ones to dedicated cleaners)
    for c in use_cols:
        if c in ("reviews.rating", "latitude", "longitude"):
            continue
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip()
            df[c] = df[c].replace({"nan": None, "None": None, "": None})

    # Normalize numerics safely
    df["reviews.rating"] = df["reviews.rating"].apply(to_int)
    # Don’t trust column dtype—coerce per-row later too

    db: Session = SessionLocal()
    created_products = 0
    created_users = 0
    created_feedback = 0

    product_cache: dict[tuple[str, str|None], int] = {}
    user_cache: dict[str, int] = {}

    try:
        for i, row in enumerate(df.to_dict(orient="records"), start=1):
            # -------- PRODUCT (get or create) --------
            name = to_none(row.get("name"))
            address = to_none(row.get("address"))
            key = (name, address)

            pid = product_cache.get(key)
            if pid is None:
                prod = (
                    db.query(Product)
                    .filter(Product.name == name, Product.address == address)
                    .first()
                )
                if prod is None:
                    prod = Product(
                        name=name,
                        categories=to_none(row.get("categories")),
                        address=address,
                        city=to_none(row.get("city")),
                        province=to_none(row.get("province")),
                        country=to_none(row.get("country")),
                        postalCode=clean_postal(row.get("postalCode")),
                        latitude=to_float_or_none(row.get("latitude")),
                        longitude=to_float_or_none(row.get("longitude")),
                    )
                    db.add(prod)
                    db.flush()  # obtain prod.id
                    created_products += 1
                pid = prod.id
                product_cache[key] = pid

            # -------- USER (get or create by username) --------
            username = to_none(row.get("reviews.username"))
            uid = None
            if username:
                uid = user_cache.get(username)
                if uid is None:
                    u = db.query(User).filter(User.username == username).first()
                    if u is None:
                        u = User(
                            username=username,
                            user_city=to_none(row.get("reviews.userCity")),
                            user_province=to_none(row.get("reviews.userProvince")),
                        )
                        db.add(u)
                        db.flush()
                        created_users += 1
                    uid = u.id
                    user_cache[username] = uid

            # -------- FEEDBACK (always create) --------
            rev_date = row.get("reviews.date")
            # NaT/NaN/None -> None; Timestamp -> datetime
            if pd.isna(rev_date):
                rev_date = None
            elif hasattr(rev_date, "to_pydatetime"):
                rev_date = rev_date.to_pydatetime()

            text_val = to_none(row.get("reviews.text"))

            fb = Feedback(
                product_id=pid,
                user_id=uid,
                rating=to_int(row.get("reviews.rating")),
                title=to_none(row.get("reviews.title")),
                text=text_val,
                review_date=rev_date,
                sentiment_label=None,
                text_length=len(text_val) if isinstance(text_val, str) else 0,
            )
            db.add(fb)
            created_feedback += 1

            if i % 1000 == 0:
                db.commit()
                print(f"...processed {i} rows (new: products={created_products}, users={created_users}, feedback={created_feedback})")

        db.commit()
        print(f"✅ Done. New products: {created_products}")
        print(f"✅ Done. New users: {created_users}")
        print(f"✅ Done. Feedback rows: {created_feedback}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
