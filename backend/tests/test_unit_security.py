import hashlib
import pytest

from backend.dam.security import check_password, hash_key, hash_password


class TestSecurityHashKey:
    def test_hash_key_returns_sha256_hex(self):
        key = "my-test-api-key"
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert hash_key(key) == expected
        assert len(hash_key(key)) == 64

    def test_hash_key_distinct_inputs(self):
        assert hash_key("key-a") != hash_key("key-b")

    def test_hash_key_empty_string(self):
        expected = hashlib.sha256(b"").hexdigest()
        assert hash_key("") == expected


class TestSecurityPasswordHashing:
    def test_hash_password_structure(self):
        stored = hash_password("secret-password")
        parts = stored.split("$")
        assert len(parts) == 2
        salt, digest = parts
        assert len(salt) == 32  # 16 bytes as hex
        assert len(digest) == 64  # sha256 hex digest

    def test_hash_password_custom_salt(self):
        custom_salt = "abcd1234efgh5678"
        stored1 = hash_password("secret-password", salt=custom_salt)
        stored2 = hash_password("secret-password", salt=custom_salt)
        assert stored1 == stored2
        assert stored1.startswith(f"{custom_salt}$")

    def test_hash_password_unique_salts_by_default(self):
        stored1 = hash_password("same-password")
        stored2 = hash_password("same-password")
        assert stored1 != stored2
        assert stored1.split("$")[0] != stored2.split("$")[0]

    def test_check_password_success(self):
        stored = hash_password("correct-horse-battery")
        assert check_password("correct-horse-battery", stored) is True

    def test_check_password_failure_wrong_password(self):
        stored = hash_password("correct-horse-battery")
        assert check_password("wrong-password", stored) is False

    def test_check_password_case_sensitive(self):
        stored = hash_password("Password123")
        assert check_password("password123", stored) is False

    def test_check_password_empty_password(self):
        stored = hash_password("")
        assert check_password("", stored) is True
        assert check_password("non-empty", stored) is False

    def test_check_password_malformed_hash(self):
        # A stored hash that doesn't match should return False
        assert check_password("test", "corruptsalt$corruptdigest") is False
