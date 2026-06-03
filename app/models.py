import os, re, unicodedata
from sqlalchemy import (
    create_engine, Column, Integer, String, Text,
    Boolean, DateTime, ForeignKey, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://medsel:medsel2024@localhost:5432/medsel")

engine = create_engine(DATABASE_URL, poolclass=NullPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "item"


class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True)
    username   = Column(String(80), unique=True, nullable=False)
    name       = Column(String(150), nullable=False)
    password   = Column(String(255), nullable=False)
    role       = Column(String(20), default="viewer")   # admin | editor | viewer
    active     = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Section(Base):
    __tablename__ = "sections"
    id         = Column(Integer, primary_key=True)
    slug       = Column(String(120), unique=True, nullable=False)
    name       = Column(String(150), nullable=False)
    icon       = Column(String(20), default="📁")       # emoji ou nome lucide
    color      = Column(String(20), default="#2563a8")  # cor do card
    order      = Column(Integer, default=99)
    active     = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    pages = relationship("Page", back_populates="section",
                         cascade="all, delete-orphan",
                         order_by="Page.order")


class Page(Base):
    __tablename__ = "pages"
    id          = Column(Integer, primary_key=True)
    section_id  = Column(Integer, ForeignKey("sections.id", ondelete="CASCADE"))
    slug        = Column(String(200), nullable=False)
    title       = Column(String(200), nullable=False)
    content     = Column(Text, default="")   # HTML do editor rico
    order       = Column(Integer, default=99)
    active      = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    section     = relationship("Section", back_populates="pages")
    attachments = relationship("Attachment", back_populates="page",
                               cascade="all, delete-orphan")


class Attachment(Base):
    __tablename__ = "attachments"
    id         = Column(Integer, primary_key=True)
    page_id    = Column(Integer, ForeignKey("pages.id", ondelete="CASCADE"))
    filename   = Column(String(255), nullable=False)   # original name shown
    stored_as  = Column(String(255), nullable=False)   # uuid filename on disk
    mime_type  = Column(String(100), default="")
    size_bytes = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    page = relationship("Page", back_populates="attachments")
