from sqlalchemy import Column, String, Float, DateTime, PrimaryKeyConstraint
from app.db.database import Base

class OHLCV(Base):
    __tablename__ = "ohlcv"
    
    time = Column(DateTime(timezone=True), primary_key=True)
    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    
    __table_args__ = (
        PrimaryKeyConstraint('time', 'symbol', 'timeframe'),
    )