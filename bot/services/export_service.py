"""Экспорт записей в Excel."""
from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Font

from bot.db.models import Appointment


def export_appointments_to_xlsx(appointments: list[Appointment]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Записи"

    headers = [
        "Дата", "Время", "Клиент", "Телефон", "Барбер",
        "Услуга", "Сумма", "Способ оплаты", "Статус",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for a in appointments:
        ws.append([
            a.datetime_start.strftime("%d.%m.%Y"),
            a.datetime_start.strftime("%H:%M"),
            a.user.name if a.user else "—",
            a.user.phone if a.user else "—",
            a.barber.name if a.barber else "—",
            a.service.name if a.service else "—",
            a.service.price if a.service else 0,
            "Предоплата" if a.payment_method == "prepaid" else "Наличные",
            {
                "pending": "Ожидает оплаты",
                "confirmed": "Подтверждена",
                "canceled": "Отменена",
                "completed": "Завершена",
            }.get(a.status, a.status),
        ])

    for col in ws.columns:
        max_len = max(len(str(c.value)) if c.value else 0 for c in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 4

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()