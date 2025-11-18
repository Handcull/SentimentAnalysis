import pandas as pd
import math
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Product

CSV_PATH = "data/7282_1.csv"

def to_none(x):
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    return x

def main():
    # Read only the columns we need
    use_cols = [
        "name","categories","address","city","province","country",
        "postalCode","latitude","longitude"
    ]
    df = pd.read_csv(CSV_PATH, usecols=use_cols)

    # Clean NAs → None and strip whitespace
    for c in use_cols:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip().replace({"nan": None})
        else:
            df[c] = df[c].apply(to_none)

    # Deduplicate products by (name, address) combo
    df = df.drop_duplicates(subset=["name", "address"])

    # Insert
    db: Session = SessionLocal()
    try:
        created = 0
        for row in df.itertuples(index=False):
            # Skip if already exists (by name + address)
            exists = db.query(Product).filter(
                Product.name == getattr(row, "name"),
                Product.address == getattr(row, "address")
            ).first()
            if exists:
                continue

            prod = Product(
                name=getattr(row, "name"),
                categories=getattr(row, "categories"),
                address=getattr(row, "address"),
                city=getattr(row, "city"),
                province=getattr(row, "province"),
                country=getattr(row, "country"),
                postalCode=getattr(row, "postalCode"),
                latitude=(float(getattr(row, "latitude")) if to_none(getattr(row, "latitude")) is not None else None),
                longitude=(float(getattr(row, "longitude")) if to_none(getattr(row, "longitude")) is not None else None),
            )
            db.add(prod)
            created += 1
            if created % 500 == 0:
                db.commit()  # commit in batches
        db.commit()
        print(f"Imported products: {created}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
