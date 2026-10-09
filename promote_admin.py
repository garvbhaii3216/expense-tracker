"""
Administrator Promotion CLI Utility
Safely grants or revokes administrative rights for existing accounts without wiping or modifying existing records.
Usage:
    python promote_admin.py <email>
"""
import sys
import os
from dotenv import load_dotenv

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
load_dotenv()

from backend.database import SessionLocal
from backend.models import User

def promote_user(email: str):
    email = email.strip().lower()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"[!] User with email '{email}' was not found in the database.")
            users = db.query(User).all()
            if users:
                print("[*] Available registered accounts:")
                for u in users:
                    print(f"    - ID {u.id}: {u.email} ({u.full_name}) [Admin: {u.is_admin}]")
            return False

        user.is_admin = True
        db.commit()
        db.refresh(user)
        print("=" * 60)
        print(f"[+] SUCCESS: User '{user.email}' ({user.full_name}) is now an Administrator!")
        print(f"[+] Admin Status: {user.is_admin}")
        print("=" * 60)
        print("[*] Next steps:")
        print("    1. Sign in or refresh the page at http://127.0.0.1:8000")
        print("    2. The 'Admin' tab will be visible in the navigation bar.")
        print("    3. Click 'Admin' to access user management, audit logs, and telemetry.")
        print("=" * 60)
        return True
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_email = sys.argv[1]
    else:
        target_email = input("Enter email to promote to Administrator: ").strip()

    if target_email:
        promote_user(target_email)
    else:
        print("[!] No email provided. Aborting.")
