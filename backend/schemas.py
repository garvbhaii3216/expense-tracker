import html
import re
from datetime import datetime as DateTimeType, date as DateType
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


def sanitize_text(v: Optional[str]) -> Optional[str]:
    """Strip dangerous characters, HTML tags, and scripts to prevent stored/reflected XSS."""
    if v is None:
        return None
    # Strip null bytes
    cleaned = v.replace("\x00", "").strip()
    # Remove script, iframe, object, embed tags and their contents
    cleaned = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<\s*object[^>]*>.*?<\s*/\s*object\s*>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<\s*embed[^>]*>.*?<\s*/\s*embed\s*>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    # Strip all other HTML tags
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    # Strip javascript: schemes
    cleaned = re.sub(r"javascript\s*:", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


# User Schemas
class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    password: str = Field(..., min_length=8, max_length=72, description="Min 8 chars, max 72 bytes")
    currency_symbol: Optional[str] = Field("₹", max_length=5)
    currency_code: Optional[str] = Field("INR", max_length=10)
    admin_secret: Optional[str] = Field(None, max_length=100, description="Optional key to create admin account")

    @field_validator("full_name")
    @classmethod
    def sanitize_full_name(cls, v: str) -> str:
        cleaned = sanitize_text(v)
        if not cleaned or len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password cannot exceed 72 bytes.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number.")
        return v


class UserLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=150, description="Email or Mobile Number")
    password: str = Field(..., min_length=1, max_length=72)

    @field_validator("username")
    @classmethod
    def sanitize_username(cls, v: str) -> str:
        return v.strip().lower()


class AdminUpgradeRequest(BaseModel):
    admin_secret: str = Field(..., min_length=1, max_length=100)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    currency_symbol: str
    currency_code: str
    is_admin: bool = False
    is_active: bool = True
    created_at: DateTimeType


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    currency_symbol: Optional[str] = Field(None, max_length=5)
    currency_code: Optional[str] = Field(None, max_length=10)

    @field_validator("full_name")
    @classmethod
    def sanitize_name(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Allowance Cycle Schemas
class AllowanceCycleCreate(BaseModel):
    month_year: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Format YYYY-MM e.g. 2026-10")
    initial_allowance: float = Field(..., ge=0, le=100_000_000, description="Starting allowance amount")
    funding_source: Optional[str] = Field("Parents", max_length=100)
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("funding_source", "notes")
    @classmethod
    def sanitize_cycle_fields(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v)


class AllowanceCycleUpdate(BaseModel):
    initial_allowance: Optional[float] = Field(None, ge=0, le=100_000_000)
    funding_source: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("funding_source", "notes")
    @classmethod
    def sanitize_update_fields(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v)


class AllowanceCycleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    month_year: str
    initial_allowance: float
    funding_source: str
    notes: Optional[str] = None
    created_at: DateTimeType
    updated_at: DateTimeType


# Refill Log Schemas
class RefillLogCreate(BaseModel):
    amount: float = Field(..., gt=0, le=100_000_000, description="Refill amount")
    funding_source: Optional[str] = Field("Parents", max_length=100)
    reason: Optional[str] = Field(None, max_length=255)
    date: Optional[DateType] = None
    payment_mode: Optional[str] = Field("UPI", max_length=50)
    month_year: Optional[str] = Field(None, pattern=r"^(\d{4}-(0[1-9]|1[0-2]))?$")

    @field_validator("funding_source", "reason", "payment_mode")
    @classmethod
    def sanitize_refill_fields(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v)


class RefillLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    cycle_id: Optional[int] = None
    amount: float
    funding_source: str
    reason: Optional[str] = None
    date: DateType
    payment_mode: str
    created_at: DateTimeType


# Expense Schemas
class ExpenseCreate(BaseModel):
    amount: float = Field(..., gt=0, le=100_000_000, description="Expense amount")
    category: str = Field(..., min_length=2, max_length=80)
    date: DateType
    description: str = Field(..., min_length=1, max_length=255)
    payment_mode: Optional[str] = Field("UPI", max_length=50)
    receipt_note: Optional[str] = Field(None, max_length=255)
    is_essential: Optional[bool] = True

    @field_validator("description", "receipt_note", "category", "payment_mode")
    @classmethod
    def sanitize_expense_fields(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v)


class ExpenseUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0, le=100_000_000)
    category: Optional[str] = Field(None, min_length=2, max_length=80)
    date: Optional[DateType] = None
    description: Optional[str] = Field(None, min_length=1, max_length=255)
    payment_mode: Optional[str] = Field(None, max_length=50)
    receipt_note: Optional[str] = Field(None, max_length=255)
    is_essential: Optional[bool] = None

    @field_validator("description", "receipt_note", "category", "payment_mode")
    @classmethod
    def sanitize_expense_update(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v)


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    cycle_id: Optional[int] = None
    amount: float
    category: str
    date: DateType
    description: str
    payment_mode: str
    receipt_note: Optional[str] = None
    is_essential: bool
    created_at: DateTimeType


# Dashboard & Analytics Schemas
class CategorySpend(BaseModel):
    category: str
    total_amount: float
    percentage: float
    count: int
    color: str
    icon: str


class DailySpend(BaseModel):
    date: str
    day: int
    amount: float


class DashboardSummary(BaseModel):
    month_year: str
    currency_symbol: str
    initial_allowance: float
    total_refills: float
    total_budget: float
    total_spent: float
    remaining_balance: float
    spent_today: float
    spent_this_week: float
    burn_rate_percent: float
    days_in_month: int
    days_passed: int
    days_remaining: int
    daily_budget_remaining: float
    daily_average_spent: float
    category_breakdown: List[CategorySpend]
    daily_spending: List[DailySpend]
    recent_expenses: List[ExpenseResponse]
    refills: List[RefillLogResponse]


# Settlement & Parent Report Schemas
class SettlementSummary(BaseModel):
    month_year: str
    formatted_month: str
    currency_symbol: str
    user_name: str
    initial_allowance: float
    total_refills: float
    total_received: float
    total_spent: float
    remaining_balance: float
    is_deficit: bool
    deficit_or_surplus_amount: float
    essential_spent: float
    non_essential_spent: float
    category_summary: List[CategorySpend]
    itemized_expenses: List[ExpenseResponse]
    refill_history: List[RefillLogResponse]
    whatsapp_share_text: str
    parents_note: str


class ClassifyRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)

    @field_validator("description")
    @classmethod
    def sanitize_classify_desc(cls, v: str) -> str:
        return sanitize_text(v) or ""


class ClassifyResponse(BaseModel):
    category: str
    confidence: float
    matched: bool


# Admin Schemas
class AdminUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    currency_code: str
    is_admin: bool
    is_active: bool
    created_at: DateTimeType
    total_expenses_count: int = 0
    total_spent: float = 0.0


class AdminSystemStats(BaseModel):
    total_users: int
    active_users: int
    admin_users: int
    total_expenses: int
    total_spend_volume: float
    total_refills_volume: float
    environment: str
    debug_mode: bool
    rate_limiting_enabled: bool
    database_status: str


class AdminToggleUserStatus(BaseModel):
    is_active: bool
