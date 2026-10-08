from datetime import datetime, date, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
try:
    from backend.database import Base
except (ImportError, ModuleNotFoundError):
    from database import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(50), unique=True, index=True, nullable=True)
    full_name = Column(String(150), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    currency_symbol = Column(String(10), default="₹")
    currency_code = Column(String(10), default="INR")
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    allowance_cycles = relationship("AllowanceCycle", back_populates="user", cascade="all, delete-orphan")
    refills = relationship("RefillLog", back_populates="user", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="user", cascade="all, delete-orphan")


class AllowanceCycle(Base):
    __tablename__ = "allowance_cycles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month_year = Column(String(7), nullable=False, index=True)  # Format: "YYYY-MM", e.g., "2026-10"
    initial_allowance = Column(Float, default=0.0, nullable=False)
    funding_source = Column(String(100), default="Parents")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="allowance_cycles")
    refills = relationship("RefillLog", back_populates="cycle", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="cycle")


class RefillLog(Base):
    __tablename__ = "refill_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id = Column(Integer, ForeignKey("allowance_cycles.id", ondelete="CASCADE"), nullable=True, index=True)
    amount = Column(Float, nullable=False)
    funding_source = Column(String(100), default="Parents")  # e.g. "Dad", "Mom", "Self"
    reason = Column(String(255), nullable=True)  # e.g. "College books & exam fee", "Mid-month mess refill"
    date = Column(Date, default=date.today, nullable=False)
    payment_mode = Column(String(50), default="UPI")  # "UPI", "Bank Transfer", "Cash", etc.
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="refills")
    cycle = relationship("AllowanceCycle", back_populates="refills")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id = Column(Integer, ForeignKey("allowance_cycles.id", ondelete="SET NULL"), nullable=True, index=True)
    amount = Column(Float, nullable=False)
    category = Column(String(80), nullable=False, index=True)
    date = Column(Date, default=date.today, nullable=False, index=True)
    description = Column(String(255), nullable=False)
    payment_mode = Column(String(50), default="UPI")  # "UPI", "Cash", "Card", "Online"
    receipt_note = Column(String(255), nullable=True)
    is_essential = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="expenses")
    cycle = relationship("AllowanceCycle", back_populates="expenses")
