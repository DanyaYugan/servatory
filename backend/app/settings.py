"""Единый загруженный конфиг для приложения."""

from app.config import Settings

settings = Settings.load()
