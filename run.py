"""
Personal Expense & Allowance Tracker - Application Launcher
"""
import os
import sys
import uvicorn

if __name__ == "__main__":
    # Ensure stdout handles utf-8 if possible
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("RELOAD", "true").lower() == "true"

    print("=" * 65)
    print("[*] Starting Personal Expense & Allowance Tracker Server")
    print(f"[*] URL: http://{host}:{port}")
    print("[*] Responsive on Desktop and Mobile (PWA enabled)")
    print("[*] Isolated personal database per user account")
    print("=" * 65)
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload)

