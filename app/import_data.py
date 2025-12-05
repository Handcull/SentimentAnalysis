import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import SessionLocal, Base, engine
from app.models import User, Review, Product

CSV_PATH = "data/Reviewhotel.csv"


def parse_date(value):
    """Parse tanggal dari CSV ke datetime Python."""
    if pd.isna(value):
        return None

    s = str(value).strip()
    if not s:
        return None

    # buang 'Z' di belakang kalau ada
    s = s.replace("Z", "")

    # coba format ISO dulu
    try:
        return datetime.fromisoformat(s)
    except Exception:
        # fallback: coba cuma YYYY-MM-DD
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except Exception:
            return None


# =========================================================
# USERS
# =========================================================

def import_users_if_needed(db: Session, df: pd.DataFrame):
    """
    Kalau tabel users masih kosong → import semua user dari CSV.
    Isi:
      - username            ← reviews.username
      - user_city           ← reviews.userCity (kalau ada)
      - user_province       ← reviews.userProvince (kalau ada)

    Untuk setiap username, kita pilih city/province yang TIDAK NULL
    (kalau ada beberapa baris).
    """
    count_users = db.query(User).count()
    if count_users > 0:
        print(f"Tabel users sudah berisi {count_users} baris. Skip import users.")
        return

    if "reviews.username" not in df.columns:
        raise RuntimeError("Kolom 'reviews.username' tidak ditemukan di CSV!")

    print("=== IMPORT USERS DARI CSV (tabel masih kosong) ===")

    has_user_city = "reviews.userCity" in df.columns
    has_user_province = "reviews.userProvince" in df.columns

    # username -> {"city": ..., "province": ...}
    user_info = {}

    for _, row in df.iterrows():
        username = row.get("reviews.username")
        if pd.isna(username) or str(username).strip() == "":
            username = "Unknown"
        username = str(username)

        city = None
        province = None

        if has_user_city and pd.notna(row.get("reviews.userCity")):
            city = str(row["reviews.userCity"])
        if has_user_province and pd.notna(row.get("reviews.userProvince")):
            province = str(row["reviews.userProvince"])

        if username not in user_info:
            user_info[username] = {"city": city, "province": province}
        else:
            # kalau sebelumnya None, tapi sekarang ada isi → pakai yang baru
            if user_info[username]["city"] is None and city is not None:
                user_info[username]["city"] = city
            if user_info[username]["province"] is None and province is not None:
                user_info[username]["province"] = province

    print("Jumlah user unik di CSV:", len(user_info))

    for username, info in user_info.items():
        u = User(
            username=username,
            user_city=info["city"],
            user_province=info["province"],
        )
        db.add(u)

    db.commit()
    print("Import users selesai.")





def build_user_map(db: Session) -> dict:
    """Ambil semua user dari DB → buat mapping username → user_id."""
    users = db.query(User).all()
    user_map = {u.username: u.id for u in users}
    print(f"User map dibuat: {len(user_map)} username.")
    return user_map


# =========================================================
# PRODUCTS (HOTEL)
# =========================================================

def import_products_if_needed(db: Session, df: pd.DataFrame):
    """
    Import hotel ke tabel products, pakai kolom:
      - name      (nama hotel)
      - city
      - province
      - country
      - address
      - postalCode
      - latitude
      - longitude

    Supaya aman dengan model Product yang mungkin beda,
    kita pakai kwargs dinamis (dicek dengan hasattr).
    """
    count_products = db.query(Product).count()
    if count_products > 0:
        print(f"Tabel products sudah berisi {count_products} baris. Skip import products.")
        return

    print("=== IMPORT PRODUCTS (HOTEL) DARI CSV ===")

    if "name" not in df.columns:
        raise RuntimeError("Kolom 'name' (nama hotel) tidak ditemukan di CSV!")

    cols = []
    for col in ["name", "city", "province", "country", "address", "postalCode", "latitude", "longitude"]:
        if col in df.columns:
            cols.append(col)

    prod_df = df[cols].drop_duplicates(subset=["name", "city", "province"], keep="first")

    print("Jumlah hotel unik di CSV:", len(prod_df))

    inserted = 0
    for _, row in prod_df.iterrows():
        name = str(row["name"]) if pd.notna(row["name"]) else "Unknown Hotel"

        kwargs = {"name": name}

        # isi field lain kalau memang ada di model Product
        if "city" in cols and hasattr(Product, "city"):
            kwargs["city"] = str(row["city"]) if pd.notna(row["city"]) else None
        if "province" in cols and hasattr(Product, "province"):
            kwargs["province"] = str(row["province"]) if pd.notna(row["province"]) else None
        if "country" in cols and hasattr(Product, "country"):
            kwargs["country"] = str(row["country"]) if pd.notna(row["country"]) else None
        if "address" in cols and hasattr(Product, "address"):
            kwargs["address"] = str(row["address"]) if pd.notna(row["address"]) else None
        if "postalCode" in cols and hasattr(Product, "postal_code"):
            kwargs["postal_code"] = str(row["postalCode"]) if pd.notna(row["postalCode"]) else None
        if "latitude" in cols and hasattr(Product, "latitude"):
            try:
                kwargs["latitude"] = float(row["latitude"]) if pd.notna(row["latitude"]) else None
            except Exception:
                kwargs["latitude"] = None
        if "longitude" in cols and hasattr(Product, "longitude"):
            try:
                kwargs["longitude"] = float(row["longitude"]) if pd.notna(row["longitude"]) else None
            except Exception:
                kwargs["longitude"] = None

        p = Product(**kwargs)
        db.add(p)
        inserted += 1

        if inserted % 1000 == 0:
            db.commit()
            print(f"{inserted} products sudah di-insert...")

    db.commit()
    print(f"Import products selesai. Total {inserted} hotel dimasukkan.")


def build_product_map(db: Session) -> dict:
    """Mapping nama hotel → product_id."""
    products = db.query(Product).all()
    prod_map = {}
    for p in products:
        key = (p.name or "").strip()
        if key and key not in prod_map:
            prod_map[key] = p.id
    print(f"Product map dibuat: {len(prod_map)} hotel.")
    return prod_map


# =========================================================
# REVIEWS
# =========================================================

def import_reviews(db: Session, df: pd.DataFrame):
    """
    Import semua review ke tabel reviews.
    - Pakai user_id dari user_map
    - Pakai product_id berdasarkan nama hotel (kolom 'name')
    """
    print("=== IMPORT REVIEWS DARI CSV ===")

    if "reviews.username" not in df.columns:
        raise RuntimeError("Kolom 'reviews.username' tidak ditemukan di CSV!")
    if "name" not in df.columns:
        raise RuntimeError("Kolom 'name' (nama hotel) tidak ditemukan di CSV!")

    # cek dulu apakah tabel reviews sudah kosong
    count_reviews = db.query(Review).count()
    if count_reviews > 0:
        print(f"WARNING: tabel reviews sudah berisi {count_reviews} baris.")
        print("Untuk menghindari duplikasi, sebaiknya kosongkan dulu tabel reviews.")
        return

    # map user & product
    user_map = build_user_map(db)
    product_map = build_product_map(db)

    inserted = 0

    for _, row in df.iterrows():
        username = row["reviews.username"] if pd.notna(row["reviews.username"]) else "Unknown"
        username = str(username)

        # pastikan user ada
        if username not in user_map:
            new_user = User(username=username, user_city=None, user_province=None)
            db.add(new_user)
            db.flush()
            user_map[username] = new_user.id

        user_id = user_map[username]

        # cari product_id dari nama hotel
        hotel_name = str(row["name"]) if pd.notna(row["name"]) else ""
        key = hotel_name.strip()
        product_id = product_map.get(key)

        # kalau belum ada di product_map, buat product baru minimal name saja
        if product_id is None:
            p = Product(name=hotel_name or "Unknown Hotel")
            db.add(p)
            db.flush()
            product_id = p.id
            product_map[key] = product_id

        rating = None
        if "reviews.rating" in df.columns and pd.notna(row["reviews.rating"]):
            try:
                rating = int(row["reviews.rating"])
            except Exception:
                rating = None

        title = row["reviews.title"] if "reviews.title" in df.columns and pd.notna(row["reviews.title"]) else None
        text = row["reviews.text"] if "reviews.text" in df.columns and pd.notna(row["reviews.text"]) else None
        review_date = parse_date(row["reviews.date"]) if "reviews.date" in df.columns else None

        review = Review(
            product_id=product_id,
            user_id=user_id,
            rating=rating,
            title=title,
            text=text,
            review_date=review_date,
            sentiment_label=None,
            polarity=None,
            subjectivity=None,
        )

        db.add(review)
        inserted += 1

        if inserted % 1000 == 0:
            db.commit()
            print(f"{inserted} reviews sudah di-insert...")

    db.commit()
    print(f"Import reviews selesai. Total {inserted} baris dimasukkan.")


# =========================================================
# MAIN
# =========================================================

def main():
    print("Membaca CSV...")
    df = pd.read_csv(CSV_PATH)

    # BUAT / CEK TABEL
    print("Mengecek & membuat tabel jika belum ada...")
    Base.metadata.create_all(bind=engine)
    print("Selesai membuat tabel.")

    db = SessionLocal()

    import_users_if_needed(db, df)
    import_products_if_needed(db, df)
    import_reviews(db, df)

    db.close()


if __name__ == "__main__":
    main()
