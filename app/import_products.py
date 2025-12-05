import pandas as pd
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Product

# Lokasi CSV (kamu sudah taruh di folder data/)
CSV_PATH = "data/Reviewhotel.csv"


def _clean_str(value):
    """Ubah NaN -> None, selain itu jadi string dan strip spasi."""
    if pd.isna(value):
        return None
    return str(value).strip()


def import_products():
    print("Membaca CSV...")
    df = pd.read_csv(CSV_PATH)

    print(f"Jumlah baris CSV: {len(df)}")

    print("Mengambil hotel unik (berdasarkan name, city, province, country, postalCode, latitude, longitude)...")
    hotels = df[[
        "name",
        "city",
        "province",
        "country",
        "postalCode",
        "latitude",
        "longitude",
    ]].drop_duplicates()

    print(f"Jumlah hotel unik: {len(hotels)}")

    db: Session = SessionLocal()

    count = 0
    for _, row in hotels.iterrows():
        # Bersihkan string (handle NaN -> None)
        name = _clean_str(row.get("name"))
        city = _clean_str(row.get("city"))
        province = _clean_str(row.get("province"))
        country = _clean_str(row.get("country"))
        postal = _clean_str(row.get("postalCode"))

        # Kalau name kosong/NaN, skip saja (nggak masuk akal ada hotel tanpa nama)
        if not name:
            continue

        # Latitude & longitude (NaN -> None)
        lat_raw = row.get("latitude")
        if pd.isna(lat_raw):
            latitude = None
        else:
            latitude = float(lat_raw)

        lng_raw = row.get("longitude")
        if pd.isna(lng_raw):
            longitude = None
        else:
            longitude = float(lng_raw)

        product = Product(
            name=name,
            city=city,
            province=province,
            country=country,
            latitude=latitude,
            longitude=longitude,
        )
        db.add(product)
        count += 1

    db.commit()
    db.close()

    print(f"Selesai. Total hotel ditambahkan ke tabel products: {count}")


if __name__ == "__main__":
    import_products()
