from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True, index=True)
    claim = Column(Text, nullable=False)
    status = Column(String, default="created")
    created_at = Column(DateTime, nullable=False)

    sources = relationship(
        "Source",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )

    events = relationship(
        "Event",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )

    trends = relationship(
        "TrendSignal",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )

    evidence = relationship(
        "EvidenceItem",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(
        Integer,
        ForeignKey("investigations.id"),
        nullable=False,
    )

    title = Column(Text, nullable=False)
    snippet = Column(Text, nullable=True)

    url = Column(Text, nullable=False)
    publisher = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True)
    source_type = Column(String, nullable=True)
    search_purpose = Column(String, nullable=True)
    relevance = Column(Float, nullable=True)

    investigation = relationship(
        "Investigation",
        back_populates="sources",
    )


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(
        Integer,
        ForeignKey("investigations.id"),
        nullable=False,
    )

    description = Column(Text, nullable=False)
    event_date = Column(DateTime, nullable=True)
    entities = Column(Text, nullable=True)

    investigation = relationship(
        "Investigation",
        back_populates="events",
    )


class TrendSignal(Base):
    __tablename__ = "trend_signals"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(
        Integer,
        ForeignKey("investigations.id"),
        nullable=False,
    )

    query = Column(String, nullable=False)
    peak = Column(Float, nullable=True)
    peak_date = Column(String, nullable=True)
    timeline = Column(Text, nullable=True)

    investigation = relationship(
        "Investigation",
        back_populates="trends",
    )


class EvidenceItem(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(
        Integer,
        ForeignKey("investigations.id"),
        nullable=False,
    )

    claim = Column(Text, nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)

    evidence_relationship = Column(String, nullable=False)
    explanation = Column(Text, nullable=True)

    investigation = relationship(
        "Investigation",
        back_populates="evidence",
    )
