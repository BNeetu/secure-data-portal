"""
Run this once after first install to create the initial admin account:

    cd backend
    python -m app.seed_admin

It will prompt for a username and password (or read from env vars
SEED_ADMIN_USERNAME / SEED_ADMIN_PASSWORD for non-interactive setup,
e.g. in a Docker entrypoint).

After running, it prints the TOTP provisioning URI / secret so you can
scan it into Google Authenticator / Microsoft Authenticator before the
first login (the login flow will also show a QR code automatically on
first login if you skip this step).
"""
import getpass
import os
import sys

from app.core.security import generate_totp_secret, get_totp_uri, hash_password, validate_password_strength
from app.core.user_store import create_user, get_user


def main():
    print("=" * 60)
    print(" Secure Data Portal — Initial Admin Setup")
    print("=" * 60)

    username = os.environ.get("SEED_ADMIN_USERNAME") or input("Admin username: ").strip()
    if not username:
        print("Username cannot be empty.")
        sys.exit(1)

    if get_user(username):
        print(f"User '{username}' already exists. Aborting.")
        sys.exit(1)

    password = os.environ.get("SEED_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Admin password (min 12 chars, mixed case, digit, symbol): ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.")
            sys.exit(1)

    err = validate_password_strength(password)
    if err:
        print(f"Weak password: {err}")
        sys.exit(1)

    secret = generate_totp_secret()
    create_user(username, hash_password(password), "admin", secret)

    uri = get_totp_uri(username, secret)
    print("\n✅ Admin user created successfully.\n")
    print(f"Username: {username}")
    print(f"Role:     admin")
    print(f"\nTOTP secret (manual entry):  {secret}")
    print(f"\nProvisioning URI (for QR code generators):\n{uri}")
    print("\nScan this into Google Authenticator / Microsoft Authenticator,")
    print("or it will also be shown as a QR code on your first login.\n")


if __name__ == "__main__":
    main()
