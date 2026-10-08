from datetime import datetime as DateTimeType, date as DateType, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# User Schemas
class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    password: str = Field(..., min_length=6, max_length=100)
    currency_symbol: Optional[str] = "₹"
    currency_code: Optional[str] = "INR"


class UserLogin(BaseModel):
    username: str = Field(..., description="Email or Mobile Number")
    password: str = Field(...)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    currency_symbol: str
    currency_code: str
    created_at: DateTimeType


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    currency_symbol: Optional[str] = None
    currency_code: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Allowance Cycle Schemas
class AllowanceCycleCreate(BaseModel):
    month_year: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Format YYYY-MM e.g. 2026-10")
    initial_allowance: float = Field(..., ge=0, description="Starting allowance amount, e.g. 5000.0")
    funding_source: Optional[str] = Field("Parents", description="e.g. Parents, Dad, Mom, Scholarship")
    notes: Optional[str] = None


class AllowanceCycleUpdate(BaseModel):
    initial_allowance: Optional[float] = Field(None, ge=0)
    funding_source: Optional[str] = None
    notes: Optional[str] = None


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
    amount: float = Field(..., gt=0, description="Refill amount, e.g. 1500.0")
    funding_source: Optional[str] = Field("Parents", description="e.g. Dad, Mom, Guardian")
    reason: Optional[str] = Field(None, description="Reason for mid-month top up")
    date: Optional[DateType] = None
    payment_mode: Optional[str] = Field("UPI", description="UPI, Cash, Bank Transfer, Card")
    month_year: Optional[str] = None  # YYYY-MM if specifying for particular cycle


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
    amount: float = Field(..., gt=0, description="Expense amount")
    category: str = Field(..., min_length=2, max_length=80)
    date: DateType
    description: str = Field(..., min_length=1, max_length=255)
    payment_mode: Optional[str] = Field("UPI", max_length=50)
    receipt_note: Optional[str] = Field(None, max_length=255)
    is_essential: Optional[bool] = True


class ExpenseUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    category: Optional[str] = None
    date: Optional[DateType] = None
    description: Optional[str] = None
    payment_mode: Optional[str] = None
    receipt_note: Optional[str] = None
    is_essential: Optional[bool] = None


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
    description: str


class ClassifyResponse(BaseModel):
    category: str
    confidence: float
    matched: bool

