"""
Personal Expense & Allowance Tracker - Application Launcher
Production-ready server launcher with secure defaults (debug/reload off by default).
"""
import os
import sys
from dotenv import load_dotenv
import uvicorn

# Load local environment if present
load_dotenv()

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    # Debug reload is disabled by default for security in production environments
    reload = os.environ.get("RELOAD", "false").lower() == "true"

    print("=" * 65)
    print("[*] Starting Personal Expense & Allowance Tracker Server")
    print(f"[*] URL: http://{host}:{port}")
    print(f"[*] Security Mode: {'DEBUG/RELOAD ENABLED' if reload else 'PRODUCTION SECURE (Debug Off)'}")
    print("=" * 65)
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload)
