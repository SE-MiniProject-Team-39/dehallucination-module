"""Bootstrap local credentials without shipping shared default passwords."""
import secrets
import sys
from pathlib import Path


def init():
    path = Path('.env')
    if path.exists():
        raise SystemExit('.env already exists; edit it explicitly to avoid replacing your configuration.')
    admin = secrets.token_urlsafe(16)
    reviewer = secrets.token_urlsafe(16)
    api_key = secrets.token_urlsafe(32)
    path.write_text(f'DATABASE_URL=sqlite:///./dam.db\nDAM_ADMIN_PASSWORD={admin}\nDAM_REVIEWER_PASSWORD={reviewer}\nDAM_API_KEY={api_key}\nDAM_DB_PASSWORD={secrets.token_urlsafe(24)}\nDAM_SESSION_SECRET={secrets.token_hex(32)}\nDAM_LIVE_SOURCES=false\nDAM_SECURE_COOKIES=false\n', encoding='utf-8')
    print('Created .env (ignored by Git). Credentials are stored there for local development.')
    print('Dashboard usernames: admin, reviewer. API application: demo-app.')


if __name__ == '__main__':
    if sys.argv[1:] == ['init']:
        init()
    else:
        print('Usage: python manage.py init')
