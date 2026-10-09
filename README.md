# Personal Expense & Allowance Tracker

A modern, responsive full-stack web and mobile application designed to track monthly allowances given by family members and manage day-to-day household or personal expenses with transparent settlement reporting.

---

## 🌟 Key Features

### 1. Cross-Platform Compatibility (Desktop & Mobile PWA)
- **Responsive Layout**: Adapts seamlessly to laptops/desktops with a comprehensive sidebar, expanded charts, and multi-column tables, as well as mobile devices with an app-style bottom navigation bar, floating action buttons, and touch-optimized cards.
- **Progressive Web App (PWA)**: Includes `manifest.json` and `sw.js` (Service Worker) enabling users to install the app on Android, iOS, or Chrome as a standalone mobile application.

### 2. Secure Authentication & Personal Database Isolation
- **Dual Credential Sign-In**: Login using **Email Address** or **Mobile Phone Number**.
- **Cryptographic Security**: Passwords hashed securely using `bcrypt`.
- **JWT Authorization**: Session management via JSON Web Tokens.
- **Strict Data Isolation**: Every user gets their own isolated database partition via foreign key relationships (`user_id`). Data never overlaps between different accounts.
- **Demo Quick-Fill**: One-click student demo account button for instant testing.

### 3. Core Dashboard & Allowance Management
- **Starting Monthly Allowance Tracker**: Set initial monthly funds (e.g. ₹5,000 at the beginning of the month) with source tags (Parents, Dad, Mom).
- **Dynamic Real-Time Balance**: Deducts daily expenditures from the remaining balance instantly upon logging.
- **Consumption & Burn-Down Gauge**: Visual gauge with color-coded safety indicators (Green for healthy surplus, Amber for <15% remaining, Crimson for deficit).
- **Daily Safe Spend Recommendation**: Automatically calculates remaining safe spend per day based on days left in the month.

### 4. Mid-Month Refill & Parent Settlement Option
- **Mid-Month Refills**: Log emergency or additional funds sent mid-month (e.g., "Dad sent ₹2,000 for textbooks"), updating available funds without breaking the starting allowance baseline.
- **Parent Settlement Breakdown Generator**: Generates transparent financial accountability statements:
  - Base allowance received + mid-month refills.
  - Categorized breakdown and essential vs. discretionary ratio.
  - Complete itemized list with dates and payment references.
  - Automated note for parents explaining any deficits or savings.
  - **1-Click WhatsApp Share**: Directly generates WhatsApp-ready text with bullet points and totals.
  - **1-Click Copy Statement**: Copies formatted accounting summary.
  - **Print / PDF Export**: Formatted stylesheet for clean physical printing or PDF archiving.

### 5. Day-to-Day Expense Logging & History
- **Quick Add Form**: Amount, Category (Food, Groceries, Transport, Books, Utilities, Medical, etc.), Date, Payment Mode (UPI, Cash, Card), Description, and Receipt Reference.
- **Interactive Visual Analytics**:
  - Donut Chart for category distributions.
  - Day-by-Day timeline bar chart.
- **Filtering & Search**: Live keyword search, category chips, and multi-criteria sorting (Newest, Oldest, Highest, Lowest).
- **Excel / CSV Export**: Instant UTF-8 BOM CSV download for spreadsheets.

---

## 📂 Architecture & Directory Structure

```
e:\Antigravity project\
├── .venv/                   # Python 3.13 virtual environment
├── backend/
│   ├── database.py          # SQLAlchemy SQLite connection and session maker
│   ├── models.py            # User, AllowanceCycle, RefillLog, and Expense models
│   ├── schemas.py           # Pydantic v2 validation models
│   ├── auth.py              # Bcrypt password hashing & PyJWT token utilities
│   ├── main.py              # FastAPI app, API routers, and static file serving
│   └── tests/
│       └── test_api.py      # Automated test suite (6 tests passing)
├── static/
│   ├── index.html           # Responsive Single-Page Application (HTML5 + Tailwind)
│   ├── app.js               # Frontend application state, charts, and API client
│   ├── styles.css           # Custom animations, safe-area padding, and print styles
│   ├── manifest.json        # PWA configuration
│   └── sw.js                # Service Worker for offline asset caching
├── requirements.txt         # Frozen Python dependencies
├── run.py                   # Server startup runner script
├── start.bat                # Windows quick launcher
└── README.md                # Documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+ (Python 3.13 tested)
- A modern web browser (Chrome, Edge, Firefox, Safari)

### 2. Start the Application

You can start the server in one of two ways:

#### Option A: Using the batch launcher (Windows)
Double-click `start.bat` or run:
```cmd
start.bat
```

#### Option B: Using the terminal
```powershell
# Activate the virtual environment
.venv\Scripts\activate

# Launch the server
python run.py
```

Open your browser at:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🧪 Running Automated Tests

Run the test suite with pytest:
```powershell
.venv\Scripts\python.exe -m pytest backend/tests/test_api.py -v
```

All 6 unit and integration tests verify:
1. User registration & dual-login (email or mobile).
2. Complete data isolation between multiple users.
3. Allowance cycle creation & real-time balance calculations.
4. Mid-month refills updating cycle budget and deficit resolution.
5. Settlement breakdown and WhatsApp message formatting.
6. CSV download and static frontend asset delivery.

---

## 📜 License
MIT License.
