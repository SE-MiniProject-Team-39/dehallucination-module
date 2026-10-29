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
    salt = stored.split('$')[0]
    return hmac.compare_digest(hash_password(password, salt), stored)
