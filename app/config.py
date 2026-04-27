import os
from dataclasses import dataclass


@dataclass
class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://netflix:netflix@db:5432/netflix",
    )
    CSV_PATH: str = os.getenv("CSV_PATH", "/data/netflix.csv")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    JWT_ALG: str = "HS256"
    JWT_TTL_MIN: int = int(os.getenv("JWT_TTL_MIN", "60"))


settings = Settings()
