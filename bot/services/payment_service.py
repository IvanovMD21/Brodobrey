"""Работа с ЮKassa API (тестовый магазин)."""
from __future__ import annotations

import uuid
from typing import Optional

import aiohttp
from loguru import logger

from bot.config import config


YOOKASSA_API = "https://api.yookassa.ru/v3"


def _auth() -> aiohttp.BasicAuth:
    return aiohttp.BasicAuth(
        login=config.yookassa_shop_id,
        password=config.yookassa_secret_key,
    )


async def create_payment(
    amount: int,
    description: str,
    metadata: dict,
    return_url: Optional[str] = None,
) -> Optional[dict]:
    """Создаёт платёж и возвращает ответ ЮKassa."""
    if not config.yookassa_shop_id or not config.yookassa_secret_key:
        logger.error("ЮKassa не настроена (нет SHOP_ID/SECRET_KEY)")
        return None

    idempotence_key = str(uuid.uuid4())
    payload = {
        "amount": {"value": f"{amount}.00", "currency": "RUB"},
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": return_url or config.yookassa_return_url,
        },
        "description": description,
        "metadata": metadata,
    }

    headers = {
        "Idempotence-Key": idempotence_key,
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{YOOKASSA_API}/payments",
                auth=_auth(),
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    logger.error(f"ЮKassa create_payment error: {resp.status} {data}")
                    return None
                return data
    except Exception as e:
        logger.exception(f"ЮKassa create_payment exception: {e}")
        return None


async def create_refund(payment_yookassa_id: str, amount: int) -> Optional[dict]:
    """Возврат средств по платежу."""
    idempotence_key = str(uuid.uuid4())
    payload = {
        "payment_id": payment_yookassa_id,
        "amount": {"value": f"{amount}.00", "currency": "RUB"},
    }
    headers = {
        "Idempotence-Key": idempotence_key,
        "Content-Type": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{YOOKASSA_API}/refunds",
                auth=_auth(),
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    logger.error(f"ЮKassa refund error: {resp.status} {data}")
                    return None
                return data
    except Exception as e:
        logger.exception(f"ЮKassa refund exception: {e}")
        return None