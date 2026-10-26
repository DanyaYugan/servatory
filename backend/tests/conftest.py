"""Общие настройки тестов: данные и конфиг во временном каталоге."""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="servatory-test-")

os.environ.setdefault("SERVATORY_DATA", _TMP)
os.environ.setdefault("SERVATORY_PORT", "8090")

from app import db  # noqa: E402

db.init_db()
