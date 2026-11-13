"""Конфигурация бота — читается из .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from dotenv import load_dotenv

load_dotenv()


def _parse_time(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_id: int

    yookassa_shop_id: str
    yookassa_secret_key: str
    yookassa_test_mode: bool
    yookassa_return_url: str

    webhook_base_url: str
    webhook_port: int

    work_start: time
    work_end: time
    lunch_start: time
    lunch_end: time
    slot_step_min: int

    cancel_unpaid_before_min: int

    db_url: str
    log_level: str


def load_config() -> Config:
    return Config(
        bot_token=os.getenv("BOT_TOKEN", ""),
        admin_id=int(os.getenv("ADMIN_ID", "0")),

        yookassa_shop_id=os.getenv("YOOKASSA_SHOP_ID", ""),
        yookassa_secret_key=os.getenv("YOOKASSA_SECRET_KEY", ""),
        yookassa_test_mode=os.getenv("YOOKASSA_TEST_MODE", "true").lower() == "true",
        yookassa_return_url=os.getenv("YOOKASSA_RETURN_URL", ""),

        webhook_base_url=os.getenv("WEBHOOK_BASE_URL", ""),
        webhook_port=int(os.getenv("WEBHOOK_PORT", "8080")),

        work_start=_parse_time(os.getenv("WORK_START", "10:00")),
        work_end=_parse_time(os.getenv("WORK_END", "22:00")),
        lunch_start=_parse_time(os.getenv("LUNCH_START", "14:00")),
        lunch_end=_parse_time(os.getenv("LUNCH_END", "15:00")),
        slot_step_min=int(os.getenv("SLOT_STEP_MIN", "30")),

        cancel_unpaid_before_min=int(os.getenv("CANCEL_UNPAID_BEFORE_MIN", "30")),

        db_url=os.getenv("DB_URL", "sqlite+aiosqlite:///./brodobrey.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


config = load_config()