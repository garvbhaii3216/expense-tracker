// Personal Expense & Allowance Tracker - Frontend Application Logic

// ==========================================
// CORE SECURITY UTILITY: XSS PREVENTION
// ==========================================
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ==========================================
// APPLICATION STATE
// ==========================================
let state = {
  token: localStorage.getItem("token") || null,
  user: JSON.parse(localStorage.getItem("user") || "null"),
  currentMonthYear: getInitialMonthYear(),
  categories: [],
  dashboardData: null,
  expenses: [],
  refills: [],
  settlementData: null,
  activeTab: "dashboard",
  categoryFilter: "All",
  searchQuery: "",
  sortBy: "date_desc",
  isDarkMode: localStorage.getItem("theme") === "dark",
  charts: {
    donut: null,
    bar: null
  }
};

function getInitialMonthYear() {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}

function formatMonthLabel(monthYear) {
  const [year, month] = monthYear.split("-");
  const dateObj = new Date(parseInt(year), parseInt(month) - 1, 1);
  return dateObj.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function getCurrency() {
  return (state.user && state.user.currency_symbol) ? state.user.currency_symbol : "₹";
}

function formatCurrency(amount) {
  const sym = getCurrency();
  const num = Number(amount) || 0;
  return `${sym}${num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}


// ==========================================
// TOAST NOTIFICATIONS
// ==========================================
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  const bgColors = {
    success: "bg-emerald-600 text-white",
    error: "bg-rose-600 text-white",
    info: "bg-indigo-600 text-white",
    warning: "bg-amber-500 text-white"
  };

  const icons = {
    success: "check-circle",
    error: "alert-triangle",
    info: "info",
    warning: "alert-circle"
  };

  toast.className = `pointer-events-auto flex items-center gap-2 px-4 py-3 rounded-2xl shadow-lg text-xs font-semibold transform transition-all duration-300 translate-y-2 opacity-0 ${bgColors[type] || bgColors.info}`;
  toast.innerHTML = `
    <i data-lucide="${icons[type] || 'info'}" class="w-4 h-4 flex-shrink-0"></i>
    <span>${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);
  lucide.createIcons();

  requestAnimationFrame(() => {
    toast.classList.remove("translate-y-2", "opacity-0");
  });

  setTimeout(() => {
    toast.classList.add("translate-y-2", "opacity-0");
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}


// ==========================================
// API CONFIGURATION & DYNAMIC BASE RESOLUTION
// ==========================================
// Automatically detects if the frontend is loaded from file:// or an alternative dev port (e.g., 5500, 3000)
// and connects to the FastAPI backend at http://127.0.0.1:8000.
const API_BASE = (() => {
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol;
  const port = window.location.port;
  if (proto === "file:" || (port && port !== "8000")) {
    return "http://127.0.0.1:8000";
  }
  return "";
})();

function getApiUrl(endpoint) {
  if (!endpoint) return "";
  if (endpoint.startsWith("http://") || endpoint.startsWith("https://")) {
    return endpoint;
  }
  const clean = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  return `${API_BASE}${clean}`;
}

function formatNetworkError(err) {
  if (!err) return "An unexpected error occurred.";
  const msg = err.message || String(err);
  if (
    msg.toLowerCase().includes("failed to fetch") ||
    msg.toLowerCase().includes("networkerror") ||
    msg.toLowerCase().includes("load failed") ||
    err.name === "TypeError"
  ) {
    return "Server offline or unreachable. Please start the backend with 'python run.py' (running at http://127.0.0.1:8000).";
  }
  return msg;
}

function updateServerStatusBadge(isOnline) {
  const dot = document.getElementById("serverStatusDot");
  const text = document.getElementById("serverStatusText");
  const badge = document.getElementById("serverStatusBadge");
  if (!dot || !text) return;

  if (isOnline) {
    dot.className = "w-2 h-2 rounded-full bg-emerald-500";
    text.textContent = "Backend Connected";
    badge?.classList.add("text-emerald-700", "dark:text-emerald-400");
  } else {
    dot.className = "w-2 h-2 rounded-full bg-rose-500";
    text.textContent = "Backend Offline (run 'python run.py')";
    badge?.classList.add("text-rose-600", "dark:text-rose-400");
  }
}

async function checkBackendHealth() {
  try {
    const res = await fetch(getApiUrl("/api/categories"), {
      method: "GET",
      headers: { "Accept": "application/json" }
    });
    if (res.ok) {
      updateServerStatusBadge(true);
      return true;
    }
  } catch (e) {
    // Backend is unreachable
  }
  updateServerStatusBadge(false);
  return false;
}

// ==========================================
// API HELPER
// ==========================================
async function apiRequest(endpoint, options = {}) {
  const url = getApiUrl(endpoint);
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };

  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }

  try {
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) {
      // Unauthorized or token expired
      logout();
      showToast("Session expired. Please sign in again.", "warning");
      return null;
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `Server error (${res.status})` }));
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    return await res.json();
  } catch (error) {
    showToast(formatNetworkError(error), "error");
    throw error;
  }
}


// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  setupEventListeners();

  // Verify backend health on startup
  checkBackendHealth();

  // Initialize Mobile App 1-Click Install detection
  initMobileInstallPrompt();

  // Service worker registration for PWA
  if ('serviceWorker' in navigator && window.location.protocol.startsWith("http")) {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.log('SW registration error:', err);
    });
  }

  if (state.token) {
    try {
      const me = await apiRequest("/api/auth/me");
      if (me) {
        state.user = me;
        localStorage.setItem("user", JSON.stringify(me));
        showApp();
        return;
      }
    } catch (e) {
      console.error(e);
    }
  }

  showAuth();
});


// ==========================================
// THEME & DOM SETUP
// ==========================================
function initTheme() {
  if (state.isDarkMode) {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
  updateThemeIcon();
}

function toggleDarkMode() {
  state.isDarkMode = !state.isDarkMode;
  localStorage.setItem("theme", state.isDarkMode ? "dark" : "light");
  initTheme();
  // Re-render charts with appropriate theme colors
  if (state.dashboardData) {
    renderCharts(state.dashboardData);
  }
}

function updateThemeIcon() {
  const icon = document.getElementById("themeIcon");
  if (icon) {
    icon.setAttribute("data-lucide", state.isDarkMode ? "sun" : "moon");
    lucide.createIcons();
  }
}


// ==========================================
// AUTHENTICATION LOGIC
// ==========================================
function setupEventListeners() {
  // Tab toggle in auth
  const tabLoginBtn = document.getElementById("tabLoginBtn");
  const tabRegisterBtn = document.getElementById("tabRegisterBtn");
  const loginForm = document.getElementById("loginForm");
  const registerForm = document.getElementById("registerForm");

  tabLoginBtn?.addEventListener("click", () => {
    tabLoginBtn.className = "w-1/2 py-2 text-sm font-semibold rounded-lg transition-all bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-sm";
    tabRegisterBtn.className = "w-1/2 py-2 text-sm font-semibold rounded-lg transition-all text-slate-600 dark:text-slate-300 hover:text-slate-900";
    loginForm.classList.remove("hidden");
    registerForm.classList.add("hidden");
  });

  tabRegisterBtn?.addEventListener("click", () => {
    tabRegisterBtn.className = "w-1/2 py-2 text-sm font-semibold rounded-lg transition-all bg-white dark:bg-slate-800 text-emerald-600 dark:text-emerald-400 shadow-sm";
    tabLoginBtn.className = "w-1/2 py-2 text-sm font-semibold rounded-lg transition-all text-slate-600 dark:text-slate-300 hover:text-slate-900";
    registerForm.classList.remove("hidden");
    loginForm.classList.add("hidden");
  });

  // Login submission
  loginForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("loginUsername").value.trim();
    const password = document.getElementById("loginPassword").value;

    try {
      const res = await fetch(getApiUrl("/api/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error((data && data.detail) || `Login failed (${res.status})`);

      state.token = data.access_token;
      state.user = data.user;
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("user", JSON.stringify(data.user));

      showToast(`Welcome back, ${data.user.full_name}!`, "success");
      showApp();
    } catch (err) {
      showToast(formatNetworkError(err), "error");
    }
  });

  // Register submission
  registerForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const full_name = document.getElementById("regFullName").value.trim();
    const email = document.getElementById("regEmail").value.trim();
    const phone = document.getElementById("regPhone").value.trim();
    const password = document.getElementById("regPassword").value;
    const adminKeyInput = document.getElementById("regAdminKey")?.value.trim();
    const currencyVal = document.getElementById("regCurrency").value.split(":");
    const currency_symbol = currencyVal[0];
    const currency_code = currencyVal[1];

    // Client-side password complexity verification
    if (password.length < 8) {
      showToast("Password must be at least 8 characters long.", "error");
      return;
    }
    if (!/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[0-9]/.test(password)) {
      showToast("Password must include at least one uppercase letter, one lowercase letter, and one number.", "error");
      return;
    }

    try {
      const payload = {
        full_name,
        email,
        phone: phone || null,
        password,
        currency_symbol,
        currency_code
      };
      if (adminKeyInput) {
        payload.admin_secret = adminKeyInput;
      }

      const res = await fetch(getApiUrl("/api/auth/register"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error((data && data.detail) || `Registration failed (${res.status})`);

      state.token = data.access_token;
      state.user = data.user;
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("user", JSON.stringify(data.user));

      if (data.user.is_admin) {
        showToast("Administrator account verified and initialized!", "success");
      } else {
        showToast("Account created successfully!", "success");
      }
      showApp();
    } catch (err) {
      showToast(formatNetworkError(err), "error");
    }
  });

  // Demo account filler
  document.getElementById("demoFillBtn")?.addEventListener("click", async () => {
    // Attempt login first with standard demo credentials
    const demoEmail = "aarav.student@example.com";
    const demoPass = "StudentPass123!";
    document.getElementById("loginUsername").value = demoEmail;
    document.getElementById("loginPassword").value = demoPass;

    try {
      const res = await fetch(getApiUrl("/api/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: demoEmail, password: demoPass })
      });
      if (res.ok) {
        const data = await res.json().catch(() => null);
        if (data && data.access_token) {
          state.token = data.access_token;
          state.user = data.user;
          localStorage.setItem("token", data.access_token);
          localStorage.setItem("user", JSON.stringify(data.user));
          showToast("Signed in as Demo Student Aarav!", "success");
          showApp();
          return;
        }
      }
    } catch (e) {}

    // If demo account doesn't exist yet, auto register it
    try {
      const regRes = await fetch(getApiUrl("/api/auth/register"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: "Aarav Sharma",
          email: demoEmail,
          phone: "+919876543210",
          password: demoPass,
          currency_symbol: "₹",
          currency_code: "INR"
        })
      });
      if (regRes.ok) {
        const data = await regRes.json().catch(() => null);
        if (data && data.access_token) {
          state.token = data.access_token;
          state.user = data.user;
          localStorage.setItem("token", data.access_token);
          localStorage.setItem("user", JSON.stringify(data.user));

          // Seed some realistic starter expenses for the demo account
          await seedDemoExpenses(data.access_token);

          showToast("Created & seeded demo account!", "success");
          showApp();
          return;
        }
      }
    } catch (e) {
      showToast(formatNetworkError(e), "error");
      return;
    }
    showToast("Demo sign-in ready. Please click Sign In.", "info");
  });

  // Expense Form submit
  document.getElementById("expenseForm")?.addEventListener("submit", handleSaveExpense);

  // Refill Form submit
  document.getElementById("refillForm")?.addEventListener("submit", handleSaveRefill);

  // Allowance Form submit
  document.getElementById("allowanceForm")?.addEventListener("submit", handleSaveAllowance);
}

async function seedDemoExpenses(token) {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const baseDate = `${year}-${month}`;

  const demoItems = [
    { amount: 350, category: "Food & Dining", date: `${baseDate}-02`, description: "Campus cafeteria lunch & snacks", payment_mode: "UPI", is_essential: true },
    { amount: 1200, category: "Books & Study", date: `${baseDate}-04`, description: "Semester reference books & stationery", payment_mode: "UPI", is_essential: true },
    { amount: 450, category: "Transport & Fuel", date: `${baseDate}-06`, description: "Monthly Metro rail recharge", payment_mode: "UPI", is_essential: true },
    { amount: 620, category: "Groceries", date: `${baseDate}-07`, description: "Milk, bread, oats, and hostel fruits", payment_mode: "Cash", is_essential: true },
  ];

  for (const item of demoItems) {
    await fetch(getApiUrl("/api/expenses"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify(item)
    }).catch(() => {});
  }
}

function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === "password") {
    input.type = "text";
    btn.innerHTML = `<i data-lucide="eye-off" class="w-4 h-4"></i>`;
  } else {
    input.type = "password";
    btn.innerHTML = `<i data-lucide="eye" class="w-4 h-4"></i>`;
  }
  lucide.createIcons();
}

function showAuth() {
  document.getElementById("authScreen")?.classList.remove("hidden");
  document.getElementById("appScreen")?.classList.add("hidden");
}

function showApp() {
  document.getElementById("authScreen")?.classList.add("hidden");
  document.getElementById("appScreen")?.classList.remove("hidden");

  // Update User Profile indicators
  if (state.user) {
    document.getElementById("userNameDisplay").textContent = state.user.full_name;
    document.getElementById("userEmailDisplay").textContent = state.user.email;
    const initial = state.user.full_name.charAt(0).toUpperCase();
    document.getElementById("userAvatar").textContent = initial;

    // Toggle Admin visibility based on role
    const adminNav = document.getElementById("nav-admin");
    const mobileAdminNav = document.getElementById("mobile-nav-admin");
    const adminUnlockBtn = document.getElementById("sidebarAdminUnlockBtn");
    if (state.user && state.user.is_admin) {
      if (adminNav) adminNav.classList.remove("hidden");
      if (mobileAdminNav) mobileAdminNav.classList.remove("hidden");
      if (adminUnlockBtn) adminUnlockBtn.classList.add("hidden");
    } else {
      if (adminNav) adminNav.classList.add("hidden");
      if (mobileAdminNav) mobileAdminNav.classList.add("hidden");
      if (adminUnlockBtn) adminUnlockBtn.classList.remove("hidden");
    }
  }

  loadCategories();
  loadDashboardData();
  switchTab("dashboard");
}

async function logout() {
  try {
    if (state.token) {
      await fetch(getApiUrl("/api/auth/logout"), {
        method: "POST",
        headers: { "Authorization": `Bearer ${state.token}` }
      });
    }
  } catch (e) {}
  state.token = null;
  state.user = null;
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  const adminNav = document.getElementById("nav-admin");
  const mobileAdminNav = document.getElementById("mobile-nav-admin");
  const adminUnlockBtn = document.getElementById("sidebarAdminUnlockBtn");
  if (adminNav) adminNav.classList.add("hidden");
  if (mobileAdminNav) mobileAdminNav.classList.add("hidden");
  if (adminUnlockBtn) adminUnlockBtn.classList.remove("hidden");
  showAuth();
  showToast("You have been securely signed out.", "info");
}


// ==========================================
// MONTH NAVIGATION
// ==========================================
function updateMonthHeader() {
  const display = document.getElementById("currentMonthDisplay");
  if (display) {
    display.textContent = formatMonthLabel(state.currentMonthYear);
  }
  const badge = document.getElementById("cycleSettingsMonthBadge");
  if (badge) {
    badge.textContent = formatMonthLabel(state.currentMonthYear);
  }
}

function prevMonth() {
  const [yearStr, monthStr] = state.currentMonthYear.split("-");
  let year = parseInt(yearStr);
  let month = parseInt(monthStr) - 1;
  if (month < 1) {
    month = 12;
    year -= 1;
  }
  state.currentMonthYear = `${year}-${String(month).padStart(2, "0")}`;
  updateMonthHeader();
  refreshCurrentView();
}

function nextMonth() {
  const [yearStr, monthStr] = state.currentMonthYear.split("-");
  let year = parseInt(yearStr);
  let month = parseInt(monthStr) + 1;
  if (month > 12) {
    month = 1;
    year += 1;
  }
  state.currentMonthYear = `${year}-${String(month).padStart(2, "0")}`;
  updateMonthHeader();
  refreshCurrentView();
}

function refreshCurrentView() {
  loadDashboardData();
  if (state.activeTab === "expenses") {
    loadExpenses();
  } else if (state.activeTab === "refills") {
    loadRefills();
  } else if (state.activeTab === "settlement") {
    loadSettlement();
  }
}


// ==========================================
// CATEGORIES LOGIC
// ==========================================
async function loadCategories() {
  try {
    const categories = await apiRequest("/api/categories");
    if (categories) {
      state.categories = categories;
      renderCategorySelects();
      renderCategoryFilterChips();
    }
  } catch (e) {
    console.error(e);
  }
}

function renderCategorySelects() {
  const select = document.getElementById("expenseCategory");
  if (!select) return;
  select.innerHTML = state.categories.map(cat => `
    <option value="${cat.name}">${cat.name}</option>
  `).join("");
}

function renderCategoryFilterChips() {
  const container = document.getElementById("categoryFilterChips");
  if (!container) return;

  const allChips = [{ name: "All", color: "#6366f1" }, ...state.categories];
  container.innerHTML = allChips.map(cat => {
    const isSelected = state.categoryFilter === cat.name;
    const activeClasses = isSelected
      ? "bg-indigo-600 text-white font-bold shadow-sm"
      : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200";

    return `
      <button onclick="setCategoryFilter('${cat.name}')" class="px-3 py-1.5 rounded-xl whitespace-nowrap text-xs transition active-press ${activeClasses}">
        ${cat.name}
      </button>
    `;
  }).join("");
}

function setCategoryFilter(categoryName) {
  state.categoryFilter = categoryName;
  renderCategoryFilterChips();
  loadExpenses();
}


// ==========================================
// DASHBOARD & SUMMARY DATA
// ==========================================
async function loadDashboardData() {
  updateMonthHeader();
  try {
    const data = await apiRequest(`/api/dashboard/summary?month_year=${state.currentMonthYear}`);
    if (!data) return;

    state.dashboardData = data;
    renderDashboardKPIs(data);
    renderCharts(data);
    renderRecentExpenses(data.recent_expenses);
    renderRefills(data.refills);
  } catch (e) {
    console.error(e);
  }
}

function renderDashboardKPIs(data) {
  // Check Zero Allowance Banner (shown if starting allowance is 0 and no refills yet)
  const zeroBanner = document.getElementById("zeroAllowanceBanner");
  if (zeroBanner) {
    if (data.initial_allowance === 0 && data.total_refills === 0) {
      zeroBanner.classList.remove("hidden");
    } else {
      zeroBanner.classList.add("hidden");
    }
  }

  // KPI 1: Total Budget (Base + Refills)
  document.getElementById("statTotalBudget").textContent = formatCurrency(data.total_budget);
  document.getElementById("statRefillNotice").textContent = `Base ${formatCurrency(data.initial_allowance)} ${data.total_refills > 0 ? `+ Refill ${formatCurrency(data.total_refills)}` : ''}`;

  // KPI 2: Total Spent
  document.getElementById("statTotalSpent").textContent = formatCurrency(data.total_spent);
  document.getElementById("statSpentCount").textContent = `${data.recent_expenses.length} expenses logged`;
  document.getElementById("statBurnPercent").textContent = `${data.burn_rate_percent}% burned`;

  // KPI 3: Remaining Balance & Alert Badge
  const balEl = document.getElementById("statRemainingBalance");
  const balBadge = document.getElementById("balanceStatusBadge");
  const balIconContainer = document.getElementById("balanceIconContainer");
  const balCard = document.getElementById("remainingBalanceCard");

  balEl.textContent = formatCurrency(data.remaining_balance);

  if (data.remaining_balance < 0) {
    // Deficit warning
    balEl.className = "text-xl sm:text-2xl font-black text-rose-600 dark:text-rose-400";
    balBadge.className = "font-bold text-rose-600 dark:text-rose-400 badge-alert";
    balBadge.textContent = "Deficit (Need Top-up)";
    balIconContainer.className = "p-1.5 rounded-lg bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400";
  } else if (data.burn_rate_percent > 85) {
    // Warning near limit
    balEl.className = "text-xl sm:text-2xl font-black text-amber-500 dark:text-amber-400";
    balBadge.className = "font-bold text-amber-600 dark:text-amber-400";
    balBadge.textContent = "Running Low (<15% left)";
    balIconContainer.className = "p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400";
  } else {
    // Healthy surplus
    balEl.className = "text-xl sm:text-2xl font-black text-emerald-600 dark:text-emerald-400";
    balBadge.className = "font-bold text-emerald-600 dark:text-emerald-400";
    balBadge.textContent = "Surplus Safe";
    balIconContainer.className = "p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400";
  }

  // KPI 4: Daily Safe Spend
  document.getElementById("statDailySafe").textContent = `${formatCurrency(data.daily_budget_remaining)}/day`;
  document.getElementById("statDaysRemaining").textContent = `${data.days_remaining} days left in cycle`;
  document.getElementById("statSpentTodayBadge").textContent = `${formatCurrency(data.spent_today)} spent today`;

  // Burn-Down Progress Bar Gauge
  const burnProgressBar = document.getElementById("burnProgressBar");
  const burnRateText = document.getElementById("burnRateText");
  const pct = Math.min(100, Math.max(0, data.burn_rate_percent));
  burnProgressBar.style.width = `${pct}%`;

  if (data.remaining_balance < 0) {
    burnProgressBar.className = "bg-rose-600 h-2.5 rounded-full transition-all duration-500";
    burnRateText.className = "text-xs font-extrabold px-2.5 py-1 rounded-full bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-400";
    burnRateText.textContent = `${data.burn_rate_percent}% (Overbudget)`;
  } else if (pct > 80) {
    burnProgressBar.className = "bg-amber-500 h-2.5 rounded-full transition-all duration-500";
    burnRateText.className = "text-xs font-extrabold px-2.5 py-1 rounded-full bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-400";
    burnRateText.textContent = `${data.burn_rate_percent}% Used`;
  } else {
    burnProgressBar.className = "bg-indigo-600 h-2.5 rounded-full transition-all duration-500";
    burnRateText.className = "text-xs font-extrabold px-2.5 py-1 rounded-full bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-400";
    burnRateText.textContent = `${data.burn_rate_percent}% Used`;
  }

  document.getElementById("burnGaugeBase").textContent = `Starting: ${formatCurrency(data.initial_allowance)}`;
  document.getElementById("burnGaugeRefill").textContent = `Refills: +${formatCurrency(data.total_refills)}`;
  document.getElementById("burnGaugeSpent").textContent = `Spent: -${formatCurrency(data.total_spent)}`;
  document.getElementById("burnGaugeLeft").textContent = `Net: ${formatCurrency(data.remaining_balance)}`;

  // Update Allowance tab inputs & views
  const cycleInitialDisplay = document.getElementById("cycleInitialDisplay");
  if (cycleInitialDisplay) cycleInitialDisplay.textContent = formatCurrency(data.initial_allowance);
}


// ==========================================
// CHARTS (Chart.js)
// ==========================================
function renderCharts(data) {
  renderCategoryDonut(data.category_breakdown);
  renderDailyBarChart(data.daily_spending);
}

function renderCategoryDonut(categories) {
  const canvas = document.getElementById("categoryDonutChart");
  const noDataEl = document.getElementById("noDataCategory");
  if (!canvas) return;

  if (state.charts.donut) {
    state.charts.donut.destroy();
  }

  if (!categories || categories.length === 0) {
    noDataEl?.classList.remove("hidden");
    return;
  }
  noDataEl?.classList.add("hidden");

  const labels = categories.map(c => c.category);
  const amounts = categories.map(c => c.total_amount);
  const colors = categories.map(c => c.color);

  state.charts.donut = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [{
        data: amounts,
        backgroundColor: colors,
        borderWidth: state.isDarkMode ? 2 : 2,
        borderColor: state.isDarkMode ? "#1e293b" : "#ffffff",
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "right",
          labels: {
            boxWidth: 12,
            font: { size: 11, family: "'Plus Jakarta Sans', sans-serif" },
            color: state.isDarkMode ? "#cbd5e1" : "#475569"
          }
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              const val = ctx.raw || 0;
              return ` ${ctx.label}: ${formatCurrency(val)}`;
            }
          }
        }
      },
      cutout: "68%"
    }
  });
}

function renderDailyBarChart(dailyList) {
  const canvas = document.getElementById("dailyBarChart");
  const noDataEl = document.getElementById("noDataDaily");
  if (!canvas) return;

  if (state.charts.bar) {
    state.charts.bar.destroy();
  }

  const hasSpend = dailyList && dailyList.some(d => d.amount > 0);
  if (!hasSpend) {
    noDataEl?.classList.remove("hidden");
    return;
  }
  noDataEl?.classList.add("hidden");

  const labels = dailyList.map(d => `${d.day}`);
  const amounts = dailyList.map(d => d.amount);

  state.charts.bar = new Chart(canvas, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        label: "Spent",
        data: amounts,
        backgroundColor: "#10b981",
        borderRadius: 4,
        maxBarThickness: 18
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              return ` Day ${ctx.label}: ${formatCurrency(ctx.raw)}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: state.isDarkMode ? "#94a3b8" : "#64748b",
            font: { size: 10 }
          }
        },
        y: {
          beginAtZero: true,
          grid: {
            color: state.isDarkMode ? "#334155" : "#f1f5f9"
          },
          ticks: {
            color: state.isDarkMode ? "#94a3b8" : "#64748b",
            font: { size: 10 },
            callback: function(val) {
              return `${getCurrency()}${val}`;
            }
          }
        }
      }
    }
  });
}


// ==========================================
// RECENT EXPENSES LIST
// ==========================================
function renderRecentExpenses(expenses) {
  const container = document.getElementById("recentExpensesList");
  if (!container) return;

  if (!expenses || expenses.length === 0) {
    container.innerHTML = `
      <div class="p-8 text-center text-xs text-slate-400">
        <i data-lucide="inbox" class="w-8 h-8 mx-auto mb-2 opacity-50"></i>
        <span>No expenses recorded for this month yet.</span>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  container.innerHTML = expenses.map(item => `
    <div class="p-3.5 sm:p-4 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-700/40 transition">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-700/80 flex items-center justify-center text-slate-700 dark:text-slate-200">
          <i data-lucide="${getCategoryIcon(item.category)}" class="w-5 h-5"></i>
        </div>
        <div>
          <div class="text-xs sm:text-sm font-bold text-slate-900 dark:text-white">${escapeHtml(item.description)}</div>
          <div class="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
            <span>${item.date}</span>
            <span>•</span>
            <span class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 font-medium">${item.category}</span>
            <span>•</span>
            <span>${item.payment_mode}</span>
          </div>
        </div>
      </div>
      <div class="text-right">
        <div class="text-xs sm:text-sm font-black text-rose-600 dark:text-rose-400">-${formatCurrency(item.amount)}</div>
        ${item.is_essential ? '<span class="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">Essential</span>' : '<span class="text-[10px] text-amber-500 font-semibold">Discretionary</span>'}
      </div>
    </div>
  `).join("");

  lucide.createIcons();
}

function getCategoryIcon(catName) {
  const found = state.categories.find(c => c.name === catName);
  return (found && found.icon) ? found.icon : "tag";
}


// ==========================================
// ALL EXPENSES VIEW (TAB 2)
// ==========================================
let filterDebounceTimer = null;
function debounceFilterExpenses() {
  clearTimeout(filterDebounceTimer);
  filterDebounceTimer = setTimeout(() => {
    state.searchQuery = document.getElementById("expenseSearchInput").value;
    loadExpenses();
  }, 250);
}

async function loadExpenses() {
  const sortSelect = document.getElementById("expenseSortSelect");
  if (sortSelect) state.sortBy = sortSelect.value;

  const params = new URLSearchParams({
    month_year: state.currentMonthYear,
    sort_by: state.sortBy
  });

  if (state.categoryFilter && state.categoryFilter !== "All") {
    params.append("category", state.categoryFilter);
  }

  if (state.searchQuery) {
    params.append("search", state.searchQuery);
  }

  try {
    const list = await apiRequest(`/api/expenses?${params.toString()}`);
    if (!list) return;

    state.expenses = list;
    renderAllExpenses(list);
  } catch (e) {
    console.error(e);
  }
}

function renderAllExpenses(expenses) {
  const container = document.getElementById("allExpensesList");
  const countText = document.getElementById("filteredCountText");
  const totalText = document.getElementById("filteredTotalText");

  const total = expenses.reduce((sum, item) => sum + item.amount, 0);
  if (countText) countText.textContent = `Showing ${expenses.length} transaction${expenses.length === 1 ? '' : 's'}`;
  if (totalText) totalText.textContent = `Total: ${formatCurrency(total)}`;

  if (!container) return;

  if (expenses.length === 0) {
    container.innerHTML = `
      <div class="p-12 text-center text-xs text-slate-400">
        <i data-lucide="search-x" class="w-8 h-8 mx-auto mb-2 opacity-50"></i>
        <span>No matching expenses found for this month filter.</span>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  container.innerHTML = expenses.map(item => `
    <div class="p-4 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-700/40 transition">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-700 flex items-center justify-center text-slate-700 dark:text-slate-200">
          <i data-lucide="${getCategoryIcon(item.category)}" class="w-5 h-5"></i>
        </div>
        <div>
          <div class="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <span>${escapeHtml(item.description)}</span>
            ${item.receipt_note ? `<span class="text-[10px] text-slate-400 italic">(${escapeHtml(item.receipt_note)})</span>` : ''}
          </div>
          <div class="text-xs text-slate-400 flex items-center gap-2 mt-0.5">
            <span>${item.date}</span>
            <span>•</span>
            <span class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 font-semibold text-[11px]">${item.category}</span>
            <span>•</span>
            <span>${item.payment_mode}</span>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-4">
        <div class="text-right">
          <div class="text-sm font-black text-rose-600 dark:text-rose-400">-${formatCurrency(item.amount)}</div>
          ${item.is_essential ? '<span class="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold">Essential</span>' : '<span class="text-[10px] text-amber-500 font-bold">Discretionary</span>'}
        </div>

        <div class="flex items-center gap-1">
          <button onclick="editExpense(${item.id})" class="p-1.5 text-slate-400 hover:text-indigo-600 rounded-lg" title="Edit Expense">
            <i data-lucide="edit-2" class="w-4 h-4"></i>
          </button>
          <button onclick="deleteExpense(${item.id})" class="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg" title="Delete Expense">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </div>
      </div>
    </div>
  `).join("");

  lucide.createIcons();
}


// ==========================================
// AI CATEGORY CLASSIFIER & INTELLIGENCE
// ==========================================
const AI_KEYWORDS = {
  "Food & Dining": [
    "canteen", "lunch", "dinner", "breakfast", "brunch", "snack", "snacks",
    "coffee", "tea", "chai", "burger", "pizza", "biryani", "swiggy", "zomato",
    "cafe", "restaurant", "hotel food", "mess", "dosa", "idli", "maggi",
    "subway", "kfc", "mcdonalds", "starbucks", "bakery", "ice cream", "dessert",
    "shawarma", "sandwich", "paneer", "roll", "momos", "thali", "juice", "eat", "meal", "food"
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
};

let userOverrodeCategory = false;
let aiClassifyDebounce = null;

function handleUserCategoryOverride() {
  userOverrodeCategory = true;
  const badge = document.getElementById("aiCategoryBadge");
  if (badge) badge.classList.add("hidden");
}

function handleDescriptionChange(text) {
  if (userOverrodeCategory) {
    if (!text || !text.trim()) {
      userOverrodeCategory = false;
    }
    return;
  }
  clearTimeout(aiClassifyDebounce);
  aiClassifyDebounce = setTimeout(() => {
    runAiCategoryClassifier(text);
  }, 150);
}

function runAiCategoryClassifier(text) {
  const clean = (text || "").toLowerCase().trim();
  const badge = document.getElementById("aiCategoryBadge");
  const badgeText = document.getElementById("aiCategoryText");
  const categorySelect = document.getElementById("expenseCategory");

  if (!clean) {
    if (badge) badge.classList.add("hidden");
    return;
  }

  let bestCat = null;
  let bestScore = 0;

  for (const [cat, words] of Object.entries(AI_KEYWORDS)) {
    let score = 0;
    for (const kw of words) {
      if (clean.includes(kw)) {
        if (clean.startsWith(kw) || clean.endsWith(kw) || clean.includes(" " + kw + " ")) {
          score += 3;
        } else {
          score += 1;
        }
      }
    }
    if (score > bestScore) {
      bestScore = score;
      bestCat = cat;
    }
  }

  if (bestCat && bestScore > 0) {
    if (categorySelect) categorySelect.value = bestCat;
    if (badge) {
      badge.classList.remove("hidden");
      if (badgeText) badgeText.textContent = `AI: ${bestCat}`;
      lucide.createIcons();
    }
  } else {
    if (badge) badge.classList.add("hidden");
  }
}


// ==========================================
// SAVED CARDS & BANKS STORAGE HELPERS
// ==========================================
function getSavedCardsKey() {
  return `saved_cards_${state.user ? state.user.id : 'guest'}`;
}

function getSavedBanksKey() {
  return `saved_banks_${state.user ? state.user.id : 'guest'}`;
}

function getSavedCards() {
  try {
    return JSON.parse(localStorage.getItem(getSavedCardsKey()) || "[]");
  } catch (e) {
    return [];
  }
}

function saveCard(cardObj) {
  if (!cardObj || !cardObj.name) return;
  const list = getSavedCards();
  const exists = list.some(c => c.name.toLowerCase() === cardObj.name.toLowerCase() && c.last4 === cardObj.last4);
  if (!exists) {
    list.push(cardObj);
    localStorage.setItem(getSavedCardsKey(), JSON.stringify(list));
  }
}

function getSavedBanks() {
  try {
    return JSON.parse(localStorage.getItem(getSavedBanksKey()) || "[]");
  } catch (e) {
    return [];
  }
}

function saveBank(bankName) {
  if (!bankName) return;
  const list = getSavedBanks();
  if (!list.includes(bankName)) {
    list.push(bankName);
    localStorage.setItem(getSavedBanksKey(), JSON.stringify(list));
  }
}


// ==========================================
// DYNAMIC PAYMENT MODE SWITCHING
// ==========================================
function handlePaymentModeChange() {
  const mode = document.getElementById("expensePaymentMode").value;
  const upiGroup = document.getElementById("upiFieldGroup");
  const cashGroup = document.getElementById("cashFieldGroup");
  const cardGroup = document.getElementById("cardFieldGroup");
  const netBankingGroup = document.getElementById("netBankingFieldGroup");

  if (upiGroup) upiGroup.classList.add("hidden");
  if (cashGroup) cashGroup.classList.add("hidden");
  if (cardGroup) cardGroup.classList.add("hidden");
  if (netBankingGroup) netBankingGroup.classList.add("hidden");

  if (mode === "UPI") {
    if (upiGroup) upiGroup.classList.remove("hidden");
  } else if (mode === "Cash") {
    if (cashGroup) cashGroup.classList.remove("hidden");
  } else if (mode === "Card") {
    if (cardGroup) cardGroup.classList.remove("hidden");
    renderSavedCardsDropdown();
  } else if (mode === "Net Banking") {
    if (netBankingGroup) netBankingGroup.classList.remove("hidden");
    renderSavedBanksDropdown();
  }
  lucide.createIcons();
}

function selectUpiApp(appName) {
  const input = document.getElementById("upiAppNameInput");
  if (input) input.value = appName;
}

function selectBankName(bankName) {
  const input = document.getElementById("bankNameInput");
  if (input) input.value = bankName;
}

function renderSavedCardsDropdown() {
  const container = document.getElementById("savedCardsContainer");
  const select = document.getElementById("savedCardsSelect");
  if (!container || !select) return;

  const cards = getSavedCards();
  if (cards.length === 0) {
    container.classList.add("hidden");
    return;
  }

  container.classList.remove("hidden");
  select.innerHTML = `
    <option value="">-- Or Pick a Saved Card --</option>
    ${cards.map((c, idx) => `
      <option value="${idx}">${escapeHtml(c.name)}${c.last4 ? ` (****${c.last4})` : ''}</option>
    `).join('')}
    <option value="new">+ Enter New Card Details</option>
  `;
}

function handleSavedCardChange() {
  const select = document.getElementById("savedCardsSelect");
  const idx = select.value;
  if (!idx || idx === "new") {
    document.getElementById("cardNameInput").value = "";
    document.getElementById("cardLastDigitsInput").value = "";
    return;
  }
  const cards = getSavedCards();
  const card = cards[parseInt(idx)];
  if (card) {
    document.getElementById("cardNameInput").value = card.name;
    document.getElementById("cardLastDigitsInput").value = card.last4 || "";
  }
}

function renderSavedBanksDropdown() {
  const container = document.getElementById("savedBanksContainer");
  const select = document.getElementById("savedBanksSelect");
  if (!container || !select) return;

  const banks = getSavedBanks();
  if (banks.length === 0) {
    container.classList.add("hidden");
    return;
  }

  container.classList.remove("hidden");
  select.innerHTML = `
    <option value="">-- Or Pick a Saved Bank --</option>
    ${banks.map(b => `<option value="${escapeHtml(b)}">${escapeHtml(b)}</option>`).join('')}
    <option value="new">+ Enter Other Bank</option>
  `;
}

function handleSavedBankChange() {
  const select = document.getElementById("savedBanksSelect");
  const val = select.value;
  if (!val || val === "new") {
    document.getElementById("bankNameInput").value = "";
    return;
  }
  document.getElementById("bankNameInput").value = val;
}


// ==========================================
// ADD / EDIT EXPENSE MODAL & ACTIONS
// ==========================================
function openAddExpenseModal() {
  userOverrodeCategory = false;
  document.getElementById("editExpenseId").value = "";
  document.getElementById("expenseModalTitle").innerHTML = `
    <i data-lucide="plus-circle" class="w-5 h-5 text-indigo-500"></i>
    <span>Add New Expense</span>
  `;
  document.getElementById("expenseAmount").value = "";
  document.getElementById("expenseDescription").value = "";
  document.getElementById("expenseEssential").checked = true;

  // Reset payment specific fields
  document.getElementById("expensePaymentMode").value = "UPI";
  document.getElementById("upiAppNameInput").value = "";
  document.getElementById("cashRemarkInput").value = "";
  document.getElementById("cardNameInput").value = "";
  document.getElementById("cardLastDigitsInput").value = "";
  document.getElementById("bankNameInput").value = "";

  // Hide AI badge initially
  const badge = document.getElementById("aiCategoryBadge");
  if (badge) badge.classList.add("hidden");

  // Set date to today
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("expenseDate").value = today;

  handlePaymentModeChange();

  document.getElementById("expenseModal").classList.remove("hidden");
  lucide.createIcons();
}

function closeExpenseModal() {
  document.getElementById("expenseModal").classList.add("hidden");
}

function editExpense(id) {
  const item = state.expenses.find(e => e.id === id) || (state.dashboardData?.recent_expenses.find(e => e.id === id));
  if (!item) return;

  userOverrodeCategory = true; // don't override category on existing item
  document.getElementById("editExpenseId").value = item.id;
  document.getElementById("expenseModalTitle").innerHTML = `
    <i data-lucide="edit-3" class="w-5 h-5 text-indigo-500"></i>
    <span>Edit Expense</span>
  `;
  document.getElementById("expenseAmount").value = item.amount;
  document.getElementById("expenseDescription").value = item.description;
  document.getElementById("expenseCategory").value = item.category;
  document.getElementById("expenseDate").value = item.date;
  document.getElementById("expensePaymentMode").value = item.payment_mode || "UPI";
  document.getElementById("expenseEssential").checked = item.is_essential;

  // Reset specific inputs
  document.getElementById("upiAppNameInput").value = "";
  document.getElementById("cashRemarkInput").value = "";
  document.getElementById("cardNameInput").value = "";
  document.getElementById("cardLastDigitsInput").value = "";
  document.getElementById("bankNameInput").value = "";

  // Parse receipt note back into payment fields
  const note = item.receipt_note || "";
  if (item.payment_mode === "UPI") {
    document.getElementById("upiAppNameInput").value = note.replace(/^UPI App:\s*/i, "").replace(/^Paid via\s*/i, "");
  } else if (item.payment_mode === "Cash") {
    document.getElementById("cashRemarkInput").value = note.replace(/^Remark:\s*/i, "").replace(/^Cash Remark:\s*/i, "");
  } else if (item.payment_mode === "Card") {
    const cardMatch = note.match(/^(?:Card:\s*)?(.*?)(?:\s*\(\*{4}(\d{4})\))?$/i);
    if (cardMatch) {
      document.getElementById("cardNameInput").value = cardMatch[1] || "";
      document.getElementById("cardLastDigitsInput").value = cardMatch[2] || "";
    } else {
      document.getElementById("cardNameInput").value = note;
    }
  } else if (item.payment_mode === "Net Banking") {
    document.getElementById("bankNameInput").value = note.replace(/^Net Banking:\s*/i, "");
  }

  handlePaymentModeChange();

  document.getElementById("expenseModal").classList.remove("hidden");
  lucide.createIcons();
}

async function handleSaveExpense(e) {
  e.preventDefault();
  const editId = document.getElementById("editExpenseId").value;
  const amount = parseFloat(document.getElementById("expenseAmount").value);
  const description = document.getElementById("expenseDescription").value.trim();
  const category = document.getElementById("expenseCategory").value;
  const date = document.getElementById("expenseDate").value;
  const payment_mode = document.getElementById("expensePaymentMode").value;
  const is_essential = document.getElementById("expenseEssential").checked;

  // Construct receipt_note according to payment mode
  let receipt_note = null;
  if (payment_mode === "UPI") {
    const upiApp = document.getElementById("upiAppNameInput").value.trim();
    if (upiApp) receipt_note = `UPI App: ${upiApp}`;
  } else if (payment_mode === "Cash") {
    const remark = document.getElementById("cashRemarkInput").value.trim();
    if (remark) receipt_note = `Remark: ${remark}`;
  } else if (payment_mode === "Card") {
    const cardName = document.getElementById("cardNameInput").value.trim();
    const last4 = document.getElementById("cardLastDigitsInput").value.trim();
    if (cardName || last4) {
      receipt_note = `Card: ${cardName}${last4 ? ` (****${last4})` : ''}`.trim();
      if (document.getElementById("saveCardCheckbox").checked && cardName) {
        saveCard({ name: cardName, last4 });
      }
    }
  } else if (payment_mode === "Net Banking") {
    const bankName = document.getElementById("bankNameInput").value.trim();
    if (bankName) {
      receipt_note = `Net Banking: ${bankName}`;
      if (document.getElementById("saveBankCheckbox").checked) {
        saveBank(bankName);
      }
    }
  }

  const payload = {
    amount,
    description,
    category,
    date,
    payment_mode,
    receipt_note: receipt_note || null,
    is_essential
  };

  try {
    if (editId) {
      await apiRequest(`/api/expenses/${editId}`, {
        method: "PUT",
        body: JSON.stringify(payload)
      });
      showToast("Expense updated successfully!", "success");
    } else {
      await apiRequest("/api/expenses", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      showToast("Expense logged & deducted from allowance!", "success");
    }

    closeExpenseModal();
    loadDashboardData();
    if (state.activeTab === "expenses") {
      loadExpenses();
    }
  } catch (err) {
    console.error(err);
  }
}

async function deleteExpense(id) {
  if (!confirm("Are you sure you want to delete this expense? The amount will be restored to your balance.")) {
    return;
  }

  try {
    await apiRequest(`/api/expenses/${id}`, { method: "DELETE" });
    showToast("Expense deleted and balance updated.", "success");
    loadDashboardData();
    loadExpenses();
  } catch (err) {
    console.error(err);
  }
}


// ==========================================
// REFILLS & TOP-UPS (TAB 3)
// ==========================================
function openRefillModal() {
  document.getElementById("refillAmount").value = "";
  document.getElementById("refillSource").value = "Parents";
  document.getElementById("refillReason").value = "";
  document.getElementById("refillDate").value = new Date().toISOString().split("T")[0];

  document.getElementById("refillModal").classList.remove("hidden");
  lucide.createIcons();
}

function closeRefillModal() {
  document.getElementById("refillModal").classList.add("hidden");
}

async function handleSaveRefill(e) {
  e.preventDefault();
  const amount = parseFloat(document.getElementById("refillAmount").value);
  const funding_source = document.getElementById("refillSource").value.trim();
  const reason = document.getElementById("refillReason").value.trim();
  const date = document.getElementById("refillDate").value;
  const payment_mode = document.getElementById("refillMode").value;

  try {
    await apiRequest("/api/refills", {
      method: "POST",
      body: JSON.stringify({
        amount,
        funding_source,
        reason: reason || "Mid-month refill",
        date,
        payment_mode,
        month_year: state.currentMonthYear
      })
    });

    showToast(`Added ${formatCurrency(amount)} mid-month refill to balance!`, "success");
    closeRefillModal();
    loadDashboardData();
    loadRefills();
  } catch (err) {
    console.error(err);
  }
}

async function loadRefills() {
  try {
    const list = await apiRequest(`/api/refills?month_year=${state.currentMonthYear}`);
    if (!list) return;
    state.refills = list;
    renderRefills(list);
  } catch (e) {
    console.error(e);
  }
}

function renderRefills(refills) {
  const container = document.getElementById("refillsListContainer");
  if (!container) return;

  if (!refills || refills.length === 0) {
    container.innerHTML = `
      <div class="py-8 text-center text-xs text-slate-400">
        <i data-lucide="refresh-ccw" class="w-8 h-8 mx-auto mb-2 opacity-50"></i>
        <span>No mid-month refills logged for this cycle yet.</span>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  container.innerHTML = refills.map(item => `
    <div class="py-3.5 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold">
          <i data-lucide="plus" class="w-4 h-4"></i>
        </div>
        <div>
          <div class="text-xs sm:text-sm font-bold text-slate-900 dark:text-white">
            ${escapeHtml(item.funding_source)}: ${escapeHtml(item.reason || 'Mid-month top-up')}
          </div>
          <div class="text-[11px] text-slate-400 mt-0.5">
            <span>${item.date}</span> • <span>${item.payment_mode}</span>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <div class="text-sm font-extrabold text-emerald-600 dark:text-emerald-400">
          +${formatCurrency(item.amount)}
        </div>
        <button onclick="deleteRefill(${item.id})" class="p-1 text-slate-400 hover:text-rose-600 rounded" title="Delete Refill">
          <i data-lucide="trash" class="w-3.5 h-3.5"></i>
        </button>
      </div>
    </div>
  `).join("");

  lucide.createIcons();
}

async function deleteRefill(id) {
  if (!confirm("Are you sure you want to delete this refill? Your available balance will be reduced accordingly.")) {
    return;
  }

  try {
    await apiRequest(`/api/refills/${id}`, { method: "DELETE" });
    showToast("Refill removed and balance adjusted.", "success");
    loadDashboardData();
    loadRefills();
  } catch (err) {
    console.error(err);
  }
}


// ==========================================
// STARTING ALLOWANCE MANAGEMENT
// ==========================================
function openSetAllowanceModal() {
  if (state.dashboardData) {
    document.getElementById("setAllowanceAmount").value = state.dashboardData.initial_allowance;
  }
  document.getElementById("allowanceModal").classList.remove("hidden");
  lucide.createIcons();
}

function closeSetAllowanceModal() {
  document.getElementById("allowanceModal").classList.add("hidden");
}

async function handleSaveAllowance(e) {
  e.preventDefault();
  const initial_allowance = parseFloat(document.getElementById("setAllowanceAmount").value);
  const funding_source = document.getElementById("setAllowanceSource").value.trim();
  const notes = document.getElementById("setAllowanceNotes").value.trim();

  try {
    await apiRequest("/api/cycles", {
      method: "POST",
      body: JSON.stringify({
        month_year: state.currentMonthYear,
        initial_allowance,
        funding_source: funding_source || "Parents",
        notes: notes || null
      })
    });

    showToast(`Starting allowance updated to ${formatCurrency(initial_allowance)}!`, "success");
    closeSetAllowanceModal();
    loadDashboardData();
  } catch (err) {
    console.error(err);
  }
}


// ==========================================
// PARENT SETTLEMENT & BREAKDOWN (TAB 4)
// ==========================================
async function loadSettlement() {
  try {
    const data = await apiRequest(`/api/settlement/summary?month_year=${state.currentMonthYear}`);
    if (!data) return;

    state.settlementData = data;
    renderSettlementSheet(data);
  } catch (e) {
    console.error(e);
  }
}

function renderSettlementSheet(data) {
  document.getElementById("settleUserMonth").textContent = `Student / User: ${data.user_name} • Period: ${data.formatted_month}`;
  
  const statusBadge = document.getElementById("settleStatusBadge");
  if (data.is_deficit) {
    statusBadge.className = "self-start sm:self-auto px-3 py-1 rounded-full text-xs font-bold bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-400";
    statusBadge.textContent = `Deficit of ${formatCurrency(data.deficit_or_surplus_amount)} Needed`;
  } else {
    statusBadge.className = "self-start sm:self-auto px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400";
    statusBadge.textContent = `Surplus Safe (${formatCurrency(data.remaining_balance)} Left)`;
  }

  document.getElementById("settleBase").textContent = formatCurrency(data.initial_allowance);
  document.getElementById("settleRefills").textContent = `+${formatCurrency(data.total_refills)}`;
  document.getElementById("settleSpent").textContent = `-${formatCurrency(data.total_spent)}`;
  document.getElementById("settleNet").textContent = formatCurrency(data.remaining_balance);

  document.getElementById("settleParentsNote").textContent = data.parents_note;

  // Category Table
  const catTbody = document.getElementById("settleCategoryTbody");
  if (catTbody) {
    catTbody.innerHTML = data.category_summary.map(cat => `
      <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/50">
        <td class="p-2.5 font-bold flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${cat.color}"></span>
          <span>${cat.category}</span>
        </td>
        <td class="p-2.5 text-center text-slate-500">${cat.count}</td>
        <td class="p-2.5 text-right font-bold">${formatCurrency(cat.total_amount)}</td>
        <td class="p-2.5 text-right font-semibold text-slate-500">${cat.percentage}%</td>
      </tr>
    `).join("");
  }

  // Itemized Table
  const itemTbody = document.getElementById("settleItemizedTbody");
  if (itemTbody) {
    itemTbody.innerHTML = data.itemized_expenses.map(exp => `
      <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/50">
        <td class="p-2.5 text-slate-500 whitespace-nowrap">${exp.date}</td>
        <td class="p-2.5 font-semibold text-slate-700 dark:text-slate-300">${exp.category}</td>
        <td class="p-2.5 font-medium text-slate-900 dark:text-white">
          ${escapeHtml(exp.description)}
          ${exp.receipt_note ? `<span class="text-[10px] text-slate-400"> (Ref: ${escapeHtml(exp.receipt_note)})</span>` : ''}
        </td>
        <td class="p-2.5 text-slate-500">${exp.payment_mode}</td>
        <td class="p-2.5 text-right font-bold text-rose-600 dark:text-rose-400">-${formatCurrency(exp.amount)}</td>
      </tr>
    `).join("");
  }

  lucide.createIcons();
}

function shareWhatsApp() {
  if (!state.settlementData) return;
  const text = state.settlementData.whatsapp_share_text;
  const url = `https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`;
  window.open(url, "_blank");
}

function copySettlementText() {
  if (!state.settlementData) return;
  navigator.clipboard.writeText(state.settlementData.whatsapp_share_text)
    .then(() => showToast("Breakdown statement copied to clipboard!", "success"))
    .catch(() => showToast("Failed to copy text", "error"));
}


// ==========================================
// CSV EXPORT
// ==========================================
function exportCSV() {
  if (!state.token) return;
  const url = getApiUrl(`/api/export/csv?month_year=${state.currentMonthYear}`);
  // Fetch with Authorization header and trigger download
  fetch(url, {
    headers: { "Authorization": `Bearer ${state.token}` }
  })
  .then(res => res.blob())
  .then(blob => {
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = `expense_report_${state.currentMonthYear}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    showToast("Downloaded monthly expense CSV report!", "success");
  })
  .catch(err => {
    showToast("Failed to download CSV", "error");
  });
}


// ==========================================
// VISUAL ANALYTICS (TAB 5)
// ==========================================
function renderVisualAnalytics() {
  if (!state.dashboardData) return;
  const data = state.dashboardData;

  document.getElementById("statDailyAverage").textContent = `${formatCurrency(data.daily_average_spent)} / day`;

  // Essential vs Non-essential
  const essentialTotal = state.settlementData ? state.settlementData.essential_spent : (data.total_spent * 0.7);
  const nonEssentialTotal = state.settlementData ? state.settlementData.non_essential_spent : (data.total_spent * 0.3);
  const total = essentialTotal + nonEssentialTotal;

  const essentialPct = total > 0 ? (essentialTotal / total * 100) : 50;
  const nonEssentialPct = total > 0 ? (nonEssentialTotal / total * 100) : 50;

  document.getElementById("barEssential").style.width = `${essentialPct}%`;
  document.getElementById("barNonEssential").style.width = `${nonEssentialPct}%`;
  document.getElementById("labelEssential").textContent = `Essential: ${formatCurrency(essentialTotal)}`;
  document.getElementById("labelNonEssential").textContent = `Discretionary: ${formatCurrency(nonEssentialTotal)}`;

  // Category progress bars
  const container = document.getElementById("analyticsCategoryBars");
  if (!container) return;

  if (!data.category_breakdown || data.category_breakdown.length === 0) {
    container.innerHTML = `<div class="text-xs text-slate-400 py-4">No expense categories to display yet.</div>`;
    return;
  }

  container.innerHTML = data.category_breakdown.map(cat => `
    <div class="space-y-1">
      <div class="flex items-center justify-between text-xs">
        <span class="font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
          <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${cat.color}"></span>
          <span>${cat.category}</span>
        </span>
        <span class="font-semibold text-slate-900 dark:text-white">${formatCurrency(cat.total_amount)} (${cat.percentage}%)</span>
      </div>
      <div class="w-full bg-slate-100 dark:bg-slate-700 rounded-full h-2 overflow-hidden">
        <div class="h-full rounded-full transition-all duration-300" style="width: ${cat.percentage}%; background-color: ${cat.color}"></div>
      </div>
    </div>
  `).join("");
}


// ==========================================
// TAB SWITCHING NAVIGATION
// ==========================================
function switchTab(tabId) {
  if (tabId === "admin") {
    if (!state.user || !state.user.is_admin) {
      showToast("Access Denied: Administrator account required.", "error");
      switchTab("dashboard");
      return;
    }
  }

  state.activeTab = tabId;

  // Hide all tab sections
  ["dashboard", "expenses", "refills", "settlement", "analytics", "admin"].forEach(t => {
    const sec = document.getElementById(`tabContent-${t}`);
    if (sec) sec.classList.add("hidden");

    // Desktop nav styles
    const navBtn = document.getElementById(`nav-${t}`);
    if (navBtn) {
      if (t === tabId) {
        navBtn.className = "nav-item w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/50";
      } else {
        navBtn.className = "nav-item w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700/50";
      }
    }

    // Mobile nav styles
    const mNavBtn = document.getElementById(`mobile-nav-${t}`);
    if (mNavBtn) {
      if (t === tabId) {
        mNavBtn.className = "flex flex-col items-center py-1.5 px-3 text-indigo-600 dark:text-indigo-400 transition font-bold";
      } else {
        mNavBtn.className = "flex flex-col items-center py-1.5 px-3 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition font-medium";
      }
    }
  });

  // Show active section
  const activeSec = document.getElementById(`tabContent-${tabId}`);
  if (activeSec) activeSec.classList.remove("hidden");

  // Page title update
  const titleMap = {
    dashboard: "Dashboard",
    expenses: "Expenses & Transactions",
    refills: "Allowance & Mid-Month Refills",
    settlement: "Parent Settlement & Report",
    analytics: "Visual Analytics",
    admin: "Admin Security & Oversight"
  };
  const titleEl = document.getElementById("pageTitle");
  if (titleEl) titleEl.textContent = titleMap[tabId] || "Dashboard";

  // Tab-specific loading
  if (tabId === "dashboard") {
    loadDashboardData();
  } else if (tabId === "expenses") {
    loadExpenses();
  } else if (tabId === "refills") {
    loadRefills();
  } else if (tabId === "settlement") {
    loadSettlement();
  } else if (tabId === "analytics") {
    loadSettlement().then(() => renderVisualAnalytics());
  } else if (tabId === "admin") {
    loadAdminData();
  }

  lucide.createIcons();
}


// ==========================================
// ADMIN DASHBOARD & TELEMETRY
// ==========================================
async function loadAdminData() {
  if (!state.user || !state.user.is_admin) return;
  try {
    const stats = await apiRequest("/api/admin/stats");
    if (stats) {
      document.getElementById("adminTotalUsers").textContent = stats.total_users;
      document.getElementById("adminActiveUsers").textContent = `${stats.active_users} Active (${stats.admin_users} Admin)`;
      document.getElementById("adminTotalExpenses").textContent = stats.total_expenses;
      document.getElementById("adminTotalSpendVol").textContent = `Spend Volume: ${formatCurrency(stats.total_spend_volume)}`;
      document.getElementById("adminDbStatus").textContent = `${stats.database_status}`;
    }

    const users = await apiRequest("/api/admin/users");
    const tbody = document.getElementById("adminUserTableBody");
    if (tbody && users) {
      if (users.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="p-6 text-center text-slate-400">No registered users found.</td></tr>`;
        return;
      }
      tbody.innerHTML = users.map(u => `
        <tr class="hover:bg-slate-50 dark:hover:bg-slate-700/40 transition">
          <td class="p-3 font-mono font-bold text-slate-500">#${u.id}</td>
          <td class="p-3 font-bold text-slate-900 dark:text-white">${escapeHtml(u.full_name)}</td>
          <td class="p-3 text-slate-500 font-mono text-[11px]">${escapeHtml(u.email)}</td>
          <td class="p-3 text-center font-semibold text-slate-700 dark:text-slate-300">${u.total_expenses_count}</td>
          <td class="p-3 text-right font-bold text-rose-600 dark:text-rose-400">-${formatCurrency(u.total_spent)}</td>
          <td class="p-3 text-center">
            ${u.is_admin ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300">Admin</span>' : '<span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">User</span>'}
          </td>
          <td class="p-3 text-center">
            ${u.is_active ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300">Active</span>' : '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300">Deactivated</span>'}
          </td>
          <td class="p-3 text-right">
            ${u.id === state.user.id ? '<span class="text-[11px] text-slate-400 italic">Current User</span>' : `
              <button onclick="toggleUserStatus(${u.id}, ${u.is_active})" class="px-2 py-1 text-[11px] font-semibold rounded-lg ${u.is_active ? 'bg-rose-50 text-rose-600 hover:bg-rose-100 dark:bg-rose-950/40' : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100 dark:bg-emerald-950/40'} transition">
                ${u.is_active ? 'Deactivate' : 'Reactivate'}
              </button>
            `}
          </td>
        </tr>
      `).join("");
      lucide.createIcons();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function refreshAdminData() {
  await loadAdminData();
  showToast("Security telemetry refreshed.", "success");
}

async function toggleUserStatus(userId, currentStatus) {
  const newStatus = !currentStatus;
  const actionName = newStatus ? "reactivate" : "deactivate";
  if (!confirm(`Are you sure you want to ${actionName} this user account?`)) return;

  try {
    const res = await apiRequest(`/api/admin/users/${userId}/toggle-status`, {
      method: "PUT",
      body: JSON.stringify({ is_active: newStatus })
    });
    if (res) {
      showToast(res.message, "success");
      loadAdminData();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}


// ==========================================
// MOBILE APP 1-CLICK INSTALL & APK DOWNLOAD
// ==========================================
let deferredInstallPrompt = null;

function isMobileDevice() {
  const userAgent = navigator.userAgent || navigator.vendor || window.opera || "";
  const isMobileUa = /android|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(userAgent);
  const isSmallScreen = window.innerWidth <= 768;
  return isMobileUa || isSmallScreen;
}

function initMobileInstallPrompt() {
  // Capture Chromium / Android PWA installation prompt
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    checkAndAutoPromptMobileInstall();
  });

  // Track successful app installs
  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    showToast("Expense Tracker installed successfully! Added to your phone screen.", "success");
    closeMobileInstallModal();
  });

  // Proactive mobile prompt for smartphones
  if (isMobileDevice()) {
    setTimeout(() => {
      checkAndAutoPromptMobileInstall();
    }, 1200);
  }
}

function checkAndAutoPromptMobileInstall() {
  // Do not prompt if already running in standalone PWA window
  const isStandalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone;
  if (isStandalone) return;

  // Do not spam if user dismissed in the current session
  if (sessionStorage.getItem("pwaModalDismissed") === "true") return;

  openMobileInstallModal();
}

function openMobileInstallModal() {
  const modal = document.getElementById("mobileInstallModal");
  if (!modal) return;
  modal.classList.remove("hidden");

  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  const iosGuide = document.getElementById("iosInstallGuide");
  const pwaBtn = document.getElementById("pwaInstallActionBtn");

  if (isIOS) {
    if (iosGuide) iosGuide.classList.remove("hidden");
    if (pwaBtn) {
      pwaBtn.innerHTML = `<i data-lucide="share" class="w-4 h-4"></i><span>Add to Home Screen</span>`;
    }
  } else {
    if (iosGuide) iosGuide.classList.add("hidden");
    if (pwaBtn) {
      pwaBtn.innerHTML = `<i data-lucide="smartphone" class="w-4 h-4"></i><span>Install App (1-Click)</span>`;
    }
  }

  if (window.lucide) lucide.createIcons();
}

function closeMobileInstallModal() {
  const modal = document.getElementById("mobileInstallModal");
  if (modal) modal.classList.add("hidden");
  sessionStorage.setItem("pwaModalDismissed", "true");
}

async function triggerPwaInstall() {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    const { outcome } = await deferredInstallPrompt.userChoice;
    if (outcome === "accepted") {
      showToast("App successfully installed to your phone!", "success");
      closeMobileInstallModal();
    }
    deferredInstallPrompt = null;
  } else {
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    if (isIOS) {
      showToast("On iOS: Tap Safari Share (box with arrow) -> 'Add to Home Screen'", "info");
    } else {
      // Direct APK download fallback
      showToast("Downloading direct Android APK package...", "info");
      window.location.href = getApiUrl("/api/download/app.apk");
      sessionStorage.setItem("pwaModalDismissed", "true");
      setTimeout(() => closeMobileInstallModal(), 1200);
    }
  }
}

function trackApkDownload() {
  showToast("Downloading ExpenseTracker.apk installer...", "success");
  sessionStorage.setItem("pwaModalDismissed", "true");
  setTimeout(() => {
    closeMobileInstallModal();
  }, 1200);
}


// ==========================================
// ADMIN UPGRADE / UNLOCK LOGIC
// ==========================================
function openAdminUpgradeModal() {
  const modal = document.getElementById("adminUpgradeModal");
  if (modal) {
    modal.classList.remove("hidden");
    const input = document.getElementById("adminUpgradeSecretInput");
    if (input) {
      input.value = "";
      input.focus();
    }
  }
  if (window.lucide) lucide.createIcons();
}

function closeAdminUpgradeModal() {
  const modal = document.getElementById("adminUpgradeModal");
  if (modal) modal.classList.add("hidden");
}

async function handleAdminUpgradeSubmit(event) {
  event.preventDefault();
  const secretInput = document.getElementById("adminUpgradeSecretInput");
  const secretKey = secretInput?.value.trim();
  if (!secretKey) {
    showToast("Please enter the admin secret key.", "error");
    return;
  }

  try {
    const res = await apiRequest("/api/auth/upgrade-admin", {
      method: "POST",
      body: JSON.stringify({ admin_secret: secretKey })
    });

    if (res && res.access_token) {
      state.token = res.access_token;
      state.user = res.user;
      localStorage.setItem("token", res.access_token);
      localStorage.setItem("user", JSON.stringify(res.user));

      // Reveal Admin Navigation Tabs
      const adminNav = document.getElementById("nav-admin");
      const mobileAdminNav = document.getElementById("mobile-nav-admin");
      const adminUnlockBtn = document.getElementById("sidebarAdminUnlockBtn");
      if (adminNav) adminNav.classList.remove("hidden");
      if (mobileAdminNav) mobileAdminNav.classList.remove("hidden");
      if (adminUnlockBtn) adminUnlockBtn.classList.add("hidden");

      closeAdminUpgradeModal();
      showToast("Administrative privileges unlocked! Switched to Admin view.", "success");
      switchTab("admin");
    }
  } catch (err) {
    // Error handled in apiRequest
  }
}
