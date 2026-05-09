"""
Unit tests for OTP pure functions in auth_service.py.
No DB access — tests only generate_otp_code, hash_otp_code, verify_otp_code.
"""
import re

import pytest

from app.services.auth_service import (
    OTP_EXPIRY_MINUTES,
    generate_otp_code,
    hash_otp_code,
    verify_otp_code,
)


def test_generate_otp_code_is_six_digits():
    code = generate_otp_code()
    assert len(code) == 6
    assert code.isdigit()


def test_generate_otp_code_is_random():
    codes = {generate_otp_code() for _ in range(50)}
    # With 1 million possible codes, 50 draws should have > 1 unique value
    assert len(codes) > 1


def test_hash_otp_code_returns_salt_colon_hex():
    hashed = hash_otp_code("123456")
    # Format: "salt:hex_digest"
    parts = hashed.split(":")
    assert len(parts) == 2
    salt, digest = parts
    assert len(salt) == 32   # 16-byte token_hex
    assert len(digest) == 64  # sha256 hex = 64 chars


def test_verify_otp_code_correct_code():
    code = "987654"
    hashed = hash_otp_code(code)
    assert verify_otp_code(code, hashed) is True


def test_verify_otp_code_wrong_code():
    hashed = hash_otp_code("123456")
    assert verify_otp_code("654321", hashed) is False


def test_verify_otp_code_empty_code():
    hashed = hash_otp_code("000000")
    assert verify_otp_code("", hashed) is False


def test_verify_otp_code_different_hashes_for_same_code():
    # Random salt means each call produces a different stored value
    code = "111111"
    h1 = hash_otp_code(code)
    h2 = hash_otp_code(code)
    assert h1 != h2
    # Both still verify correctly
    assert verify_otp_code(code, h1) is True
    assert verify_otp_code(code, h2) is True


def test_otp_expiry_minutes_is_10():
    assert OTP_EXPIRY_MINUTES == 10
