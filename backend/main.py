import io
import csv
import calendar
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List
from urllib.parse import quote

from fastapi import FastAPI, Depends, HTTPException, status, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc

from backend.database import engine, get_db, Base
from backend.models import User, AllowanceCycle, RefillLog, Expense
from backend.auth import hash_password, verify_password, create_access_token, get_current_user
from backend.schemas import (
    UserRegister, UserLogin, UserResponse, UserUpdate, TokenResponse,
    AllowanceCycleCreate, AllowanceCycleUpdate, AllowanceCycleResponse,
    RefillLogCreate, RefillLogResponse,
    ExpenseCreate, ExpenseUpdate, ExpenseResponse,
    DashboardSummary, CategorySpend, DailySpend, SettlementSummary,
    ClassifyRequest, ClassifyResponse
)

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Personal Expense & Allowance Tracker API",
    description="Full-stack API for tracking family allowances, refills, day-to-day expenses and settlement reports",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Predefined categories with colors and Lucide icons
CATEGORY_METADATA = {
    "Food & Dining": {"color": "#f97316", "icon": "utensils"},
    "Groceries": {"color": "#10b981", "icon": "shopping-bag"},
    "Transport & Fuel": {"color": "#3b82f6", "icon": "car"},
    "Books & Study": {"color": "#8b5cf6", "icon": "book-open"},
    "Bills & Utilities": {"color": "#eab308", "icon": "zap"},
    "Health & Medical": {"color": "#ef4444", "icon": "heart-pulse"},
    "Entertainment & Outings": {"color": "#ec4899", "icon": "film"},
    "Hostel & Room": {"color": "#14b8a6", "icon": "home"},
    "Emergency": {"color": "#dc2626", "icon": "alert-circle"},
    "Personal & Clothing": {"color": "#06b6d4", "icon": "user"},
    "Other": {"color": "#64748b", "icon": "tag"},
}


def get_current_month_year() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def get_or_create_cycle(db: Session, user_id: int, month_year: str) -> AllowanceCycle:
    cycle = db.query(AllowanceCycle).filter(
        AllowanceCycle.user_id == user_id,
        AllowanceCycle.month_year == month_year
    ).first()
    if not cycle:
        cycle = AllowanceCycle(
            user_id=user_id,
            month_year=month_year,
            initial_allowance=0.0,
            funding_source="Parents",
            notes="Default cycle created automatically"
        )
        db.add(cycle)
        db.commit()
        db.refresh(cycle)
    return cycle


# ==========================================
# AUTHENTICATION ROUTES
# ==========================================

@app.post("/api/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    # Check if email exists
    if db.query(User).filter(User.email == user_in.email.lower()).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )

    # Check if phone exists (if provided)
    if user_in.phone and db.query(User).filter(User.phone == user_in.phone).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this phone number already exists."
        )

    hashed_pw = hash_password(user_in.password)
    user = User(
        email=user_in.email.lower(),
        phone=user_in.phone,
        full_name=user_in.full_name,
        hashed_password=hashed_pw,
        currency_symbol=user_in.currency_symbol or "₹",
        currency_code=user_in.currency_code or "INR"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Seed initial cycle for current month with 0.0 allowance (user fills on their own)
    current_month = get_current_month_year()
    starter_cycle = AllowanceCycle(
        user_id=user.id,
        month_year=current_month,
        initial_allowance=0.0,
        funding_source="Parents",
        notes="Starting monthly allowance (to be set by user)"
    )
    db.add(starter_cycle)
    db.commit()

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@app.post("/api/auth/login", response_model=TokenResponse)
def login(login_in: UserLogin, db: Session = Depends(get_db)):
    username = login_in.username.strip().lower()
    # Search by email or phone
    user = db.query(User).filter(
        (User.email == username) | (User.phone == login_in.username.strip())
    ).first()

    if not user or not verify_password(login_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please check your email/mobile number and password."
        )

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@app.put("/api/auth/profile", response_model=UserResponse)
def update_profile(
    profile_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if profile_in.full_name is not None:
        current_user.full_name = profile_in.full_name.strip()
    if profile_in.phone is not None:
        current_user.phone = profile_in.phone.strip()
    if profile_in.currency_symbol is not None:
        current_user.currency_symbol = profile_in.currency_symbol
    if profile_in.currency_code is not None:
        current_user.currency_code = profile_in.currency_code

    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


# ==========================================
# CATEGORIES ENDPOINT
# ==========================================

@app.get("/api/categories")
def get_categories():
    return [
        {"name": name, "color": meta["color"], "icon": meta["icon"]}
        for name, meta in CATEGORY_METADATA.items()
    ]


CATEGORY_KEYWORDS = {
    "Food & Dining": [
        "canteen", "lunch", "dinner", "breakfast", "brunch", "snack", "snacks",
        "coffee", "tea", "chai", "burger", "pizza", "biryani", "swiggy", "zomato",
        "cafe", "restaurant", "hotel food", "mess", "dosa", "idli", "maggi",
        "subway", "kfc", "mcdonalds", "starbucks", "bakery", "ice cream", "dessert",
        "shawarma", "sandwich", "paneer", "roll", "momos", "thali", "juice", "eat", "meal"
    ],
    "Groceries": [
        "grocery", "groceries", "milk", "bread", "eggs", "vegetables", "fruits",
        "sabzi", "kirana", "supermarket", "d-mart", "dmart", "blinkit", "zepto",
        "instamart", "bigbasket", "rice", "dal", "flour", "atta", "spices",
        "oil", "butter", "cheese", "snack refill", "pantry", "household provisions", "soap", "toothpaste"
    ],
    "Transport & Fuel": [
        "metro", "bus", "auto", "rickshaw", "uber", "ola", "rapido", "cab", "taxi",
        "petrol", "diesel", "fuel", "gasoline", "train", "railway", "irctc",
        "flight", "toll", "parking", "scooter", "bike", "mechanic", "fare", "travel", "smartcard"
    ],
    "Books & Study": [
        "book", "books", "textbook", "notebook", "stationery", "pen", "pens",
        "pencil", "xerox", "photocopy", "printout", "spiral", "course", "udemy",
        "coursera", "tuition", "coaching", "exam fee", "form fee", "college fee",
        "library", "calculator", "lab coat", "assignment", "project print", "study"
    ],
    "Bills & Utilities": [
        "bill", "electricity", "water", "wifi", "broadband", "internet",
        "recharge", "airtel", "jio", "vi", "bsnl", "mobile recharge", "dth",
        "gas cylinder", "indane", "hp gas", "maintenance fee", "electric"
    ],
    "Health & Medical": [
        "medicine", "medical", "doctor", "hospital", "clinic", "pharmacy",
        "chemist", "apollo", "medplus", "1mg", "tablet", "syrup", "capsule",
        "bandage", "crocin", "paracetamol", "dentist", "eye checkup", "specs",
        "consultation", "lab test", "blood test", "fever", "cough"
    ],
    "Entertainment & Outings": [
        "movie", "cinema", "pvr", "inox", "film", "theatre", "netflix", "prime",
        "hotstar", "spotify", "youtube", "gaming", "game", "steam", "playstation",
        "concert", "show", "amusement", "trip", "picnic", "bowling", "outing", "club"
    ],
    "Hostel & Room": [
        "hostel", "pg fee", "room rent", "rent", "landlord", "flat rent",
        "deposit", "security deposit", "mess advance", "room maintenance", "warden"
    ],
    "Emergency": [
        "emergency", "urgent", "hospital emergency", "lost", "theft", "penalty",
        "traffic fine", "police fine", "challan", "damage", "repair urgent", "breakage"
    ],
    "Personal & Clothing": [
        "clothes", "clothing", "shirt", "t-shirt", "jeans", "trousers", "shoes",
        "slippers", "sandals", "zara", "h&m", "myntra", "ajio", "amazon fashion",
        "haircut", "salon", "barber", "parlour", "shampoo", "perfume", "deodorant",
        "facewash", "skincare", "lotion", "watch"
    ]
}


@app.post("/api/ai/classify-category", response_model=ClassifyResponse)
def ai_classify_category(req: ClassifyRequest):
    desc_clean = req.description.strip().lower()
    if not desc_clean:
        return ClassifyResponse(category="Other", confidence=0.0, matched=False)

    best_category = "Other"
    best_score = 0

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in desc_clean:
                # Give higher weight to exact whole words
                if f" {kw} " in f" {desc_clean} " or desc_clean.startswith(kw) or desc_clean.endswith(kw):
                    score += 3
                else:
                    score += 1
        if score > best_score:
            best_score = score
            best_category = category

    confidence = round(min(0.98, max(0.45, best_score * 0.25)), 2) if best_score > 0 else 0.0
    return ClassifyResponse(
        category=best_category if best_score > 0 else "Other",
        confidence=confidence,
        matched=best_score > 0
    )



# ==========================================
# ALLOWANCE CYCLE ENDPOINTS
# ==========================================

@app.get("/api/cycles", response_model=List[AllowanceCycleResponse])
def get_cycles(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cycles = db.query(AllowanceCycle).filter(
        AllowanceCycle.user_id == current_user.id
    ).order_by(desc(AllowanceCycle.month_year)).all()
    return [AllowanceCycleResponse.model_validate(c) for c in cycles]


@app.get("/api/cycles/current", response_model=AllowanceCycleResponse)
def get_current_cycle(
    month_year: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target_month = month_year or get_current_month_year()
    cycle = get_or_create_cycle(db, current_user.id, target_month)
    return AllowanceCycleResponse.model_validate(cycle)


@app.post("/api/cycles", response_model=AllowanceCycleResponse)
def set_monthly_allowance(
    cycle_in: AllowanceCycleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cycle = db.query(AllowanceCycle).filter(
        AllowanceCycle.user_id == current_user.id,
        AllowanceCycle.month_year == cycle_in.month_year
    ).first()

    if cycle:
        cycle.initial_allowance = cycle_in.initial_allowance
        if cycle_in.funding_source:
            cycle.funding_source = cycle_in.funding_source
        if cycle_in.notes is not None:
            cycle.notes = cycle_in.notes
        cycle.updated_at = datetime.now(timezone.utc)
    else:
        cycle = AllowanceCycle(
            user_id=current_user.id,
            month_year=cycle_in.month_year,
            initial_allowance=cycle_in.initial_allowance,
            funding_source=cycle_in.funding_source or "Parents",
            notes=cycle_in.notes
        )
        db.add(cycle)

    db.commit()
    db.refresh(cycle)
    return AllowanceCycleResponse.model_validate(cycle)


# ==========================================
# MID-MONTH REFILLS & TOP-UPS
# ==========================================

@app.post("/api/refills", response_model=RefillLogResponse, status_code=status.HTTP_201_CREATED)
def add_refill(
    refill_in: RefillLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    refill_date = refill_in.date or date.today()
    month_year = refill_in.month_year or f"{refill_date.year:04d}-{refill_date.month:02d}"
    cycle = get_or_create_cycle(db, current_user.id, month_year)

    refill = RefillLog(
        user_id=current_user.id,
        cycle_id=cycle.id,
        amount=refill_in.amount,
        funding_source=refill_in.funding_source or "Parents",
        reason=refill_in.reason or "Mid-month refill",
        date=refill_date,
        payment_mode=refill_in.payment_mode or "UPI"
    )
    db.add(refill)
    db.commit()
    db.refresh(refill)
    return RefillLogResponse.model_validate(refill)


@app.get("/api/refills", response_model=List[RefillLogResponse])
def get_refills(
    month_year: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target_month = month_year or get_current_month_year()
    cycle = db.query(AllowanceCycle).filter(
        AllowanceCycle.user_id == current_user.id,
        AllowanceCycle.month_year == target_month
    ).first()

    if not cycle:
        return []

    refills = db.query(RefillLog).filter(
        RefillLog.user_id == current_user.id,
        RefillLog.cycle_id == cycle.id
    ).order_by(desc(RefillLog.date), desc(RefillLog.id)).all()

    return [RefillLogResponse.model_validate(r) for r in refills]


@app.delete("/api/refills/{refill_id}")
def delete_refill(
    refill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    refill = db.query(RefillLog).filter(
        RefillLog.id == refill_id,
        RefillLog.user_id == current_user.id
    ).first()
    if not refill:
        raise HTTPException(status_code=404, detail="Refill record not found")

    db.delete(refill)
    db.commit()
    return {"message": "Refill deleted successfully"}


# ==========================================
# EXPENSES ENDPOINTS
# ==========================================

@app.post("/api/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    expense_in: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    exp_date = expense_in.date
    month_year = f"{exp_date.year:04d}-{exp_date.month:02d}"
    cycle = get_or_create_cycle(db, current_user.id, month_year)

    expense = Expense(
        user_id=current_user.id,
        cycle_id=cycle.id,
        amount=expense_in.amount,
        category=expense_in.category,
        date=exp_date,
        description=expense_in.description.strip(),
        payment_mode=expense_in.payment_mode or "UPI",
        receipt_note=expense_in.receipt_note.strip() if expense_in.receipt_note else None,
        is_essential=expense_in.is_essential if expense_in.is_essential is not None else True
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return ExpenseResponse.model_validate(expense)


@app.get("/api/expenses", response_model=List[ExpenseResponse])
def get_expenses(
    month_year: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    sort_by: Optional[str] = "date_desc",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Expense).filter(Expense.user_id == current_user.id)

    if month_year:
        try:
            year_val, month_val = map(int, month_year.split("-"))
            _, last_day = calendar.monthrange(year_val, month_val)
            m_start = date(year_val, month_val, 1)
            m_end = date(year_val, month_val, last_day)
            query = query.filter(Expense.date >= m_start, Expense.date <= m_end)
        except ValueError:
            pass

    if start_date:
        query = query.filter(Expense.date >= start_date)
    if end_date:
        query = query.filter(Expense.date <= end_date)

    if category and category != "All":
        query = query.filter(Expense.category == category)

    if search:
        search_fmt = f"%{search.strip().lower()}%"
        query = query.filter(
            func.lower(Expense.description).like(search_fmt) |
            func.lower(Expense.receipt_note).like(search_fmt)
        )

    # Sorting
    if sort_by == "date_asc":
        query = query.order_by(asc(Expense.date), asc(Expense.id))
    elif sort_by == "amount_desc":
        query = query.order_by(desc(Expense.amount), desc(Expense.date))
    elif sort_by == "amount_asc":
        query = query.order_by(asc(Expense.amount), desc(Expense.date))
    else:  # date_desc default
        query = query.order_by(desc(Expense.date), desc(Expense.id))

    expenses = query.all()
    return [ExpenseResponse.model_validate(e) for e in expenses]


@app.put("/api/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: int,
    expense_in: ExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    if expense_in.amount is not None:
        expense.amount = expense_in.amount
    if expense_in.category is not None:
        expense.category = expense_in.category
    if expense_in.date is not None:
        expense.date = expense_in.date
        month_year = f"{expense.date.year:04d}-{expense.date.month:02d}"
        cycle = get_or_create_cycle(db, current_user.id, month_year)
        expense.cycle_id = cycle.id
    if expense_in.description is not None:
        expense.description = expense_in.description.strip()
    if expense_in.payment_mode is not None:
        expense.payment_mode = expense_in.payment_mode
    if expense_in.receipt_note is not None:
        expense.receipt_note = expense_in.receipt_note.strip()
    if expense_in.is_essential is not None:
        expense.is_essential = expense_in.is_essential

    db.commit()
    db.refresh(expense)
    return ExpenseResponse.model_validate(expense)


@app.delete("/api/expenses/{expense_id}")
def delete_expense(
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    db.delete(expense)
    db.commit()
    return {"message": "Expense deleted successfully"}


# ==========================================
# DASHBOARD SUMMARY & ANALYTICS
# ==========================================

@app.get("/api/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    month_year: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target_month = month_year or get_current_month_year()
    try:
        year_val, month_val = map(int, target_month.split("-"))
    except ValueError:
        now_dt = datetime.now(timezone.utc)
        year_val, month_val = now_dt.year, now_dt.month
        target_month = f"{year_val:04d}-{month_val:02d}"

    _, days_in_month = calendar.monthrange(year_val, month_val)
    m_start = date(year_val, month_val, 1)
    m_end = date(year_val, month_val, days_in_month)

    cycle = get_or_create_cycle(db, current_user.id, target_month)

    # Refills in this cycle
    refills = db.query(RefillLog).filter(
        RefillLog.user_id == current_user.id,
        RefillLog.cycle_id == cycle.id
    ).order_by(desc(RefillLog.date)).all()
    total_refills = sum(r.amount for r in refills)

    # Total budget = Starting allowance + Refills
    total_budget = cycle.initial_allowance + total_refills

    # Expenses in this cycle/month
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.date >= m_start,
        Expense.date <= m_end
    ).order_by(desc(Expense.date), desc(Expense.id)).all()

    total_spent = sum(e.amount for e in expenses)
    remaining_balance = total_budget - total_spent

    # Calculate days logic
    today = date.today()
    if today.year == year_val and today.month == month_val:
        days_passed = today.day
        days_remaining = max(1, days_in_month - days_passed + 1)
    elif today > m_end:
        days_passed = days_in_month
        days_remaining = 0
    else:
        days_passed = 0
        days_remaining = days_in_month

    # Daily spending metrics
    daily_budget_remaining = round(max(0.0, remaining_balance) / days_remaining, 2) if days_remaining > 0 else 0.0
    daily_average_spent = round(total_spent / max(1, days_passed), 2) if days_passed > 0 else 0.0

    burn_rate_percent = round((total_spent / total_budget * 100), 1) if total_budget > 0 else (100.0 if total_spent > 0 else 0.0)

    # Spent today and this week
    spent_today = sum(e.amount for e in expenses if e.date == today)
    one_week_ago = today - timedelta(days=7)
    spent_this_week = sum(e.amount for e in expenses if e.date >= one_week_ago)

    # Category Breakdown
    category_totals = {}
    category_counts = {}
    for exp in expenses:
        category_totals[exp.category] = category_totals.get(exp.category, 0.0) + exp.amount
        category_counts[exp.category] = category_counts.get(exp.category, 0) + 1

    category_breakdown = []
    for cat_name, amt in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        pct = round((amt / total_spent * 100), 1) if total_spent > 0 else 0.0
        meta = CATEGORY_METADATA.get(cat_name, {"color": "#64748b", "icon": "tag"})
        category_breakdown.append(CategorySpend(
            category=cat_name,
            total_amount=round(amt, 2),
            percentage=pct,
            count=category_counts[cat_name],
            color=meta["color"],
            icon=meta["icon"]
        ))

    # Daily spending map for charts
    day_spend_map = {d: 0.0 for d in range(1, days_in_month + 1)}
    for exp in expenses:
        if 1 <= exp.date.day <= days_in_month:
            day_spend_map[exp.date.day] += exp.amount

    daily_spending = [
        DailySpend(
            date=f"{year_val:04d}-{month_val:02d}-{d:02d}",
            day=d,
            amount=round(day_spend_map[d], 2)
        )
        for d in range(1, days_in_month + 1)
    ]

    recent_expenses = [ExpenseResponse.model_validate(e) for e in expenses[:10]]
    refill_responses = [RefillLogResponse.model_validate(r) for r in refills]

    return DashboardSummary(
        month_year=target_month,
        currency_symbol=current_user.currency_symbol or "₹",
        initial_allowance=round(cycle.initial_allowance, 2),
        total_refills=round(total_refills, 2),
        total_budget=round(total_budget, 2),
        total_spent=round(total_spent, 2),
        remaining_balance=round(remaining_balance, 2),
        spent_today=round(spent_today, 2),
        spent_this_week=round(spent_this_week, 2),
        burn_rate_percent=burn_rate_percent,
        days_in_month=days_in_month,
        days_passed=days_passed,
        days_remaining=days_remaining,
        daily_budget_remaining=daily_budget_remaining,
        daily_average_spent=daily_average_spent,
        category_breakdown=category_breakdown,
        daily_spending=daily_spending,
        recent_expenses=recent_expenses,
        refills=refill_responses
    )


# ==========================================
# PARENT SETTLEMENT & EXPENSE BREAKDOWN REPORT
# ==========================================

@app.get("/api/settlement/summary", response_model=SettlementSummary)
def get_settlement_summary(
    month_year: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target_month = month_year or get_current_month_year()
    try:
        year_val, month_val = map(int, target_month.split("-"))
    except ValueError:
        now_dt = datetime.now(timezone.utc)
        year_val, month_val = now_dt.year, now_dt.month
        target_month = f"{year_val:04d}-{month_val:02d}"

    month_name = calendar.month_name[month_val]
    formatted_month = f"{month_name} {year_val}"

    _, days_in_month = calendar.monthrange(year_val, month_val)
    m_start = date(year_val, month_val, 1)
    m_end = date(year_val, month_val, days_in_month)

    cycle = get_or_create_cycle(db, current_user.id, target_month)

    refills = db.query(RefillLog).filter(
        RefillLog.user_id == current_user.id,
        RefillLog.cycle_id == cycle.id
    ).order_by(asc(RefillLog.date)).all()
    total_refills = sum(r.amount for r in refills)
    total_received = cycle.initial_allowance + total_refills

    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.date >= m_start,
        Expense.date <= m_end
    ).order_by(asc(Expense.date), asc(Expense.id)).all()

    total_spent = sum(e.amount for e in expenses)
    remaining_balance = total_received - total_spent
    is_deficit = remaining_balance < 0
    deficit_or_surplus_amount = abs(remaining_balance)

    essential_spent = sum(e.amount for e in expenses if e.is_essential)
    non_essential_spent = sum(e.amount for e in expenses if not e.is_essential)

    # Categories
    category_totals = {}
    category_counts = {}
    for exp in expenses:
        category_totals[exp.category] = category_totals.get(exp.category, 0.0) + exp.amount
        category_counts[exp.category] = category_counts.get(exp.category, 0) + 1

    category_summary = []
    for cat_name, amt in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        pct = round((amt / total_spent * 100), 1) if total_spent > 0 else 0.0
        meta = CATEGORY_METADATA.get(cat_name, {"color": "#64748b", "icon": "tag"})
        category_summary.append(CategorySpend(
            category=cat_name,
            total_amount=round(amt, 2),
            percentage=pct,
            count=category_counts[cat_name],
            color=meta["color"],
            icon=meta["icon"]
        ))

    sym = current_user.currency_symbol or "₹"

    # Pre-formatted WhatsApp share message
    lines = [
        f"📋 *Monthly Expense & Allowance Settlement*",
        f"👤 *Student / User:* {current_user.full_name}",
        f"📅 *Period:* {formatted_month}",
        f"────────────────────────",
        f"💰 *Starting Allowance:* {sym}{cycle.initial_allowance:,.2f}",
    ]
    if total_refills > 0:
        lines.append(f"➕ *Mid-Month Refills Received:* {sym}{total_refills:,.2f}")
        for r in refills:
            lines.append(f"   • {r.date.strftime('%d %b')}: {sym}{r.amount:,.2f} ({r.funding_source} - {r.reason or 'Refill'})")
    lines.append(f"💵 *Total Funds Available:* {sym}{total_received:,.2f}")
    lines.append(f"📉 *Total Spent:* {sym}{total_spent:,.2f}")

    if is_deficit:
        lines.append(f"⚠️ *Current Deficit:* {sym}{deficit_or_surplus_amount:,.2f} (Funds needed)")
    else:
        lines.append(f"✅ *Remaining Balance:* {sym}{remaining_balance:,.2f}")

    lines.append(f"────────────────────────")
    lines.append(f"📊 *Top Category Breakdown:*")
    for cat in category_summary[:5]:
        lines.append(f"• {cat.category}: {sym}{cat.total_amount:,.2f} ({cat.percentage}%)")

    if is_deficit:
        parents_note = (
            f"Dear Parents, here is my accounting breakdown for {formatted_month}. "
            f"I have accounted for all expenditures ({sym}{total_spent:,.2f} total spent). "
            f"Due to essential expenses, my balance has run out with a deficit of {sym}{deficit_or_surplus_amount:,.2f}. "
            f"Kindly review the attached detailed breakdown for mid-month refill settlement."
        )
    else:
        parents_note = (
            f"Dear Parents, here is my expense summary for {formatted_month}. "
            f"Out of the total {sym}{total_received:,.2f} received, I have spent {sym}{total_spent:,.2f} "
            f"and saved {sym}{remaining_balance:,.2f}."
        )

    lines.append(f"────────────────────────")
    lines.append(f"💬 _{parents_note}_")

    whatsapp_share_text = "\n".join(lines)

    return SettlementSummary(
        month_year=target_month,
        formatted_month=formatted_month,
        currency_symbol=sym,
        user_name=current_user.full_name,
        initial_allowance=round(cycle.initial_allowance, 2),
        total_refills=round(total_refills, 2),
        total_received=round(total_received, 2),
        total_spent=round(total_spent, 2),
        remaining_balance=round(remaining_balance, 2),
        is_deficit=is_deficit,
        deficit_or_surplus_amount=round(deficit_or_surplus_amount, 2),
        essential_spent=round(essential_spent, 2),
        non_essential_spent=round(non_essential_spent, 2),
        category_summary=category_summary,
        itemized_expenses=[ExpenseResponse.model_validate(e) for e in expenses],
        refill_history=[RefillLogResponse.model_validate(r) for r in refills],
        whatsapp_share_text=whatsapp_share_text,
        parents_note=parents_note
    )


# ==========================================
# EXPORT TO CSV / EXCEL REPORT
# ==========================================

@app.get("/api/export/csv")
def export_csv(
    month_year: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target_month = month_year or get_current_month_year()
    try:
        year_val, month_val = map(int, target_month.split("-"))
    except ValueError:
        year_val, month_val = datetime.utcnow().year, datetime.utcnow().month
        target_month = f"{year_val:04d}-{month_val:02d}"

    _, days_in_month = calendar.monthrange(year_val, month_val)
    m_start = date(year_val, month_val, 1)
    m_end = date(year_val, month_val, days_in_month)

    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.date >= m_start,
        Expense.date <= m_end
    ).order_by(asc(Expense.date), asc(Expense.id)).all()

    output = io.StringIO()
    # Write UTF-8 BOM for Microsoft Excel compatibility
    output.write('\ufeff')
    writer = csv.writer(output)

    writer.writerow([
        "Expense ID", "Date", "Category", f"Amount ({current_user.currency_code})",
        "Payment Mode", "Description", "Receipt/Reference", "Essential"
    ])

    for exp in expenses:
        writer.writerow([
            exp.id,
            exp.date.strftime("%Y-%m-%d"),
            exp.category,
            f"{exp.amount:.2f}",
            exp.payment_mode,
            exp.description,
            exp.receipt_note or "",
            "Yes" if exp.is_essential else "No"
        ])

    csv_data = output.getvalue()
    filename = f"expense_report_{current_user.full_name.replace(' ', '_')}_{target_month}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ==========================================
# STATIC FILES & SPA FALLBACK
# ==========================================

import os
from fastapi.responses import HTMLResponse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_dir = os.path.join(BASE_DIR, "static")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Vivixo Expense Tracker API is Running Successfully!</h1>")

@app.get("/manifest.json")
def serve_manifest():
    manifest_path = os.path.join(static_dir, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/json")
    raise HTTPException(status_code=404, detail="Manifest not found")

@app.get("/sw.js")
def serve_service_worker():
    sw_path = os.path.join(static_dir, "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Service worker not found")
