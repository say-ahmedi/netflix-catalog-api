import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

log = logging.getLogger("etl")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df["show_id"] = df["show_id"].astype(str).str.strip()

    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    df["release_year"] = pd.to_numeric(df["release_year"], errors="coerce").astype("Int64")

    df = df.where(pd.notnull(df), None)
    df = df.drop_duplicates(subset=["show_id"])
    return df


def _split_by_category_and_rating(df: pd.DataFrame) -> dict[tuple[str, str], pd.DataFrame]:
    """Group rows by (primary genre, rating). Primary genre = first item in `listed_in`."""
    df = df.copy()
    df["_primary_genre"] = (
        df["listed_in"].fillna("Unknown").str.split(",").str[0].str.strip()
    )
    df["_rating_key"] = df["rating"].fillna("Unrated")

    buckets: dict[tuple[str, str], pd.DataFrame] = {}
    for (genre, rating), chunk in df.groupby(["_primary_genre", "_rating_key"]):
        buckets[(genre, rating)] = chunk.drop(columns=["_primary_genre", "_rating_key"])
    return buckets


def load_csv_to_db(engine: Engine, csv_path: str) -> None:
    """Idempotent loader. If the table is non-empty we leave it alone."""
    path = Path(csv_path)
    if not path.exists():
        log.warning("CSV not found at %s — skipping ETL.", csv_path)
        return

    with engine.connect() as conn:
        existing = conn.execute(text("SELECT COUNT(*) FROM shows")).scalar()
    if existing and existing > 0:
        log.info("'shows' already has %d rows — skipping reload.", existing)
        return

    log.info("Loading CSV: %s", csv_path)
    df = pd.read_csv(csv_path)
    df = _clean(df)
    log.info("Rows after cleaning: %d", len(df))

    buckets = _split_by_category_and_rating(df)
    log.info("Split into %d (genre, rating) buckets", len(buckets))

    total = 0
    for (genre, rating), chunk in buckets.items():
        chunk.to_sql(
            "shows",
            engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=500,
        )
        total += len(chunk)
        log.debug("  -> %s / %s : %d rows", genre, rating, len(chunk))
    log.info("ETL done. Inserted %d rows.", total)
