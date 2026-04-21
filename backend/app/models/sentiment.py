from sqlalchemy import Column, String, Float, DateTime, Integer, Text, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.core.database import Base


class SentimentIndicator(Base):
    """Fear & Greed, AAII bull/bear sentiment time-series."""
    __tablename__ = "sentiment_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False)
    indicator = Column(String(64), nullable=False)   # fear_greed_index, aaii_bullish, ...
    value = Column(Float, nullable=True)
    label = Column(String(32), nullable=True)        # "Extreme Greed", "bullish", ...
    source = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("time", "indicator", "source", name="uq_sentiment_point"),
        Index("ix_sentiment_time", "time"),
    )


class EconomicEvent(Base):
    """Macro economic calendar events — scheduled releases."""
    __tablename__ = "economic_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_date = Column(DateTime(timezone=True), nullable=False)
    event_name = Column(String(128), nullable=False)
    country = Column(String(8), nullable=False, default="USA")
    importance = Column(String(8), nullable=False, default="medium")  # low/medium/high
    actual = Column(String(32), nullable=True)
    forecast = Column(String(32), nullable=True)
    previous = Column(String(32), nullable=True)
    source = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("event_date", "event_name", "country", name="uq_event"),
        Index("ix_event_date", "event_date"),
    )


class NewsHeadline(Base):
    """Financial news headlines cache."""
    __tablename__ = "news_headlines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    url = Column(Text, nullable=True)
    source = Column(String(64), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    query_tag = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
