from sqlalchemy import Column, String, Float, DateTime, Integer, Text, Index, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class MacroIndicator(Base):
    """Stores time-series macro data (GDP, CPI, unemployment, etc.)"""
    __tablename__ = "macro_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False)
    country_code = Column(String(3), nullable=False)   # ISO 3-letter: USA, CHN, DEU
    indicator = Column(String(64), nullable=False)     # gdp_growth, cpi_yoy, unemployment
    value = Column(Float, nullable=True)
    unit = Column(String(32), nullable=True)           # %, USD_bn, index
    source = Column(String(32), nullable=False)        # fred, worldbank, imf
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("time", "country_code", "indicator", "source", name="uq_macro_point"),
        Index("ix_macro_country_indicator", "country_code", "indicator"),
        Index("ix_macro_time", "time"),
    )


class YieldCurve(Base):
    """US Treasury yield curve snapshots"""
    __tablename__ = "yield_curves"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False)
    country_code = Column(String(3), nullable=False, default="USA")
    maturity = Column(String(8), nullable=False)       # 1m, 3m, 6m, 1y, 2y, 5y, 10y, 30y
    yield_pct = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("time", "country_code", "maturity", name="uq_yield_point"),
        Index("ix_yield_time", "time"),
    )


class MarketPrice(Base):
    """OHLCV price data for equities, FX, commodities, crypto"""
    __tablename__ = "market_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False)
    symbol = Column(String(32), nullable=False)
    asset_class = Column(String(16), nullable=False)   # equity, forex, commodity, crypto, index
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    source = Column(String(32), nullable=False, default="yfinance")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("time", "symbol", name="uq_price_point"),
        Index("ix_price_symbol_time", "symbol", "time"),
    )


class DataIngestionLog(Base):
    """Track last successful ingestion per source/indicator"""
    __tablename__ = "ingestion_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(32), nullable=False)
    indicator = Column(String(64), nullable=False)
    last_fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    records_upserted = Column(Integer, default=0)
    status = Column(String(16), default="success")    # success, failed
    error_msg = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("source", "indicator", name="uq_ingestion_log"),
    )
