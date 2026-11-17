import hashlib
import hmac
import secrets


def hash_key(key):
    return hashlib.sha256(key.encode()).hexdigest()


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600_000).hex()
    return f'{salt}${digest}'


def check_password(password, stored):
    if not isinstance(password, str) or not isinstance(stored, str):
        return False

    parts = stored.split('$')
    if len(parts) != 2:
        return False

    salt, digest = parts

    if not salt or len(digest) != 64:
        return False

    if not all(c in '0123456789abcdefABCDEF' for c in digest):
        return False

    return hmac.compare_digest(hash_password(password, salt), stored)
