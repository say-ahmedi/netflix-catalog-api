from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import (
    create_engine, Column, String, Integer, Index, select, or_, and_, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from .config import settings
from .etl import load_csv_to_db


engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Show(Base):
    __tablename__ = "shows"

    show_id      = Column(String, primary_key=True)
    type         = Column(String, index=True)
    title        = Column(String, index=True)
    director     = Column(String)
    cast         = Column("cast", String)
    country      = Column(String, index=True)
    date_added   = Column(String)
    release_year = Column(Integer, index=True)
    rating       = Column(String, index=True)
    duration     = Column(String)
    listed_in    = Column(String, index=True)
    description  = Column(String)


class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    username        = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)


Index("ix_shows_type_rating", Show.type, Show.rating)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def hash_pw(pw: str) -> str:
    return pwd_ctx.hash(pw)


def verify_pw(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw, hashed)


def make_token(sub: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_TTL_MIN)
    return jwt.encode(
        {"sub": sub, "exp": exp},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALG,
    )


def current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    creds_err = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise creds_err
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise creds_err
    except JWTError:
        raise creds_err
    user = db.scalar(select(User).where(User.username == username))
    if not user:
        raise creds_err
    return user


class RegisterIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ShowOut(BaseModel):
    show_id: str
    type: Optional[str]
    title: Optional[str]
    director: Optional[str]
    cast: Optional[str]
    country: Optional[str]
    date_added: Optional[str]
    release_year: Optional[int]
    rating: Optional[str]
    duration: Optional[str]
    listed_in: Optional[str]
    description: Optional[str]

    class Config:
        from_attributes = True


class SearchOut(BaseModel):
    total: int
    items: list[ShowOut]


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    load_csv_to_db(engine, settings.CSV_PATH)
    yield


app = FastAPI(title="Netflix Catalog API", lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"status": "ok", "docs": "/docs"}


@app.post("/auth/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if not data.username or not data.password:
        raise HTTPException(400, "Username and password required")
    if len(data.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if db.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(400, "Username already taken")
    user = User(username=data.username, hashed_password=hash_pw(data.password))
    db.add(user)
    db.commit()
    return TokenOut(access_token=make_token(user.username))


@app.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == form.username))
    if not user or not verify_pw(form.password, user.hashed_password):
        raise HTTPException(401, "Wrong username or password")
    return TokenOut(access_token=make_token(user.username))


@app.get("/shows", response_model=SearchOut)
def search_shows(
    q: Optional[str] = Query(None, description="Search in title / description / cast / director"),
    type: Optional[str] = Query(None, description="'Movie' or 'TV Show'"),
    rating: Optional[str] = None,
    country: Optional[str] = None,
    genre: Optional[str] = None,
    release_year: Optional[int] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(current_user),
):
    conds = []
    if q:
        like = f"%{q}%"
        conds.append(or_(
            Show.title.ilike(like),
            Show.description.ilike(like),
            Show.cast.ilike(like),
            Show.director.ilike(like),
        ))
    if type:
        conds.append(Show.type == type)
    if rating:
        conds.append(Show.rating == rating)
    if country:
        conds.append(Show.country.ilike(f"%{country}%"))
    if genre:
        conds.append(Show.listed_in.ilike(f"%{genre}%"))
    if release_year is not None:
        conds.append(Show.release_year == release_year)
    if year_from is not None:
        conds.append(Show.release_year >= year_from)
    if year_to is not None:
        conds.append(Show.release_year <= year_to)

    where = and_(*conds) if conds else None

    total_stmt = select(func.count()).select_from(Show)
    if where is not None:
        total_stmt = total_stmt.where(where)
    total = db.scalar(total_stmt) or 0

    stmt = select(Show)
    if where is not None:
        stmt = stmt.where(where)
    stmt = stmt.order_by(Show.title).limit(limit).offset(offset)
    items = db.scalars(stmt).all()

    return SearchOut(total=total, items=items)


@app.get("/shows/{show_id}", response_model=ShowOut)
def get_show(show_id: str, db: Session = Depends(get_db),
             _user: User = Depends(current_user)):
    show = db.get(Show, show_id)
    if not show:
        raise HTTPException(404, "Not found")
    return show


@app.get("/categories")
def categories(db: Session = Depends(get_db), _user: User = Depends(current_user)):
    rows = db.execute(select(Show.listed_in).distinct()).all()
    genres = set()
    for (val,) in rows:
        if val:
            for g in val.split(","):
                genres.add(g.strip())
    ratings = sorted(r for (r,) in db.execute(select(Show.rating).distinct()).all() if r)
    types = sorted(t for (t,) in db.execute(select(Show.type).distinct()).all() if t)
    return {
        "genres": sorted(genres),
        "ratings": ratings,
        "types": types,
    }
