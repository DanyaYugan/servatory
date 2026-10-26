"""Домены и TLS: проверки без Docker."""

import pytest

from app import tls


def test_domain_validation() -> None:
    tls.validate("panel.example.com", "admin@example.com")
    with pytest.raises(tls.TlsError):
        tls.validate("bad domain", "")
    with pytest.raises(tls.TlsError):
        tls.validate("panel.example.com", "not-mail")


def test_caddyfile_internal() -> None:
    text = tls._caddyfile("localhost", "", "servatory")
    assert "tls internal" in text
    assert "reverse_proxy servatory:8090" in text


def test_caddyfile_public() -> None:
    text = tls._caddyfile("panel.example.com", "admin@example.com", "servatory")
    assert "email admin@example.com" in text
    assert "tls internal" not in text
