# 💈 Brodobrey Telegram Bot

Бот для записи в барбершоп с оплатой через ЮKassa (тестовый магазин).

## 📋 Возможности

**Клиент:**
- Запись: услуга → барбер (или «любой») → дата → время → способ оплаты
- Предоплата через ЮKassa или наличные на месте
- «Мои записи»: отмена, перенос, оплата
- Автоматический возврат при отмене оплаченной записи
- Напоминания за 24 ч и 2 ч
- Лист ожидания

**Админ:**
- Записи на сегодня/неделю
- Клиенты с историей
- Выручка (день/неделя/месяц)
- Статус оплат
- Занятость барберов
- Управление барберами и прайсом
- Блокировка клиентов
- Отмена записей с возвратом
- Экспорт в Excel
- Лист ожидания

## 🚀 Установка

### 1. Python 3.11+

```bash
python --version  # должно быть >= 3.11
```

### 2. Клонируй и установи зависимости

```bash
git clone <repo>
cd brodobrey_bot
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### 3. Создай `.env`

Скопируй `.env.example` → `.env` и заполни:

```env
BOT_TOKEN=...       # от @BotFather
ADMIN_ID=...        # твой Telegram ID (@userinfobot)

YOOKASSA_SHOP_ID=...
YOOKASSA_SECRET_KEY=...
YOOKASSA_TEST_MODE=true
YOOKASSA_RETURN_URL=https://t.me/your_bot_username

WEBHOOK_BASE_URL=https://xxxx.ngrok-free.app
WEBHOOK_PORT=8080
```

## 💳 Получение тестового магазина ЮKassa (без ИНН)

1. Открой **https://yookassa.ru/developers/payment-acceptance/getting-started/quick-start**
2. Нажми **«Создать тестовый магазин»** (короткая ссылка — ИНН не требуется)
3. При регистрации выбери **«Перейти к тестированию платежей»**
4. В личном кабинете:
   - `Настройки → Магазин` → скопируй **ShopId**
   - `Интеграция → Ключи API` → создай и скопируй **Secret Key** (показывается 1 раз!)
5. Вставь их в `.env`

### Тестовые карты

| Параметр | Значение |
|---|---|
| Номер | `5555 5555 5555 4477` |
| Срок | любая будущая дата |
| CVC | `123` |
| 3-D Secure | `123` |

## 🌐 Ngrok для вебхуков (локально)

ЮKassa должна достучаться до твоего компа — используем ngrok.

1. Скачай: https://ngrok.com/download
2. Зарегистрируйся, получи токен
3. Запусти:

```bash
ngrok config add-authtoken <ТВОЙ_ТОКЕН>
ngrok http 8080
```

4. Скопируй URL вида `https://xxxx.ngrok-free.app`
5. Вставь в `.env` → `WEBHOOK_BASE_URL`
6. В ЛК ЮKassa: `Интеграция → HTTP-уведомления` → укажи:

```
https://xxxx.ngrok-free.app/yookassa/webhook
```

7. Активируй события: `payment.succeeded`, `payment.canceled`, `refund.succeeded`

⚠️ **Бесплатный ngrok** меняет URL при каждом запуске — не забывай обновлять его в `.env` и в ЛК ЮKassa.

## ▶️ Запуск

### Вариант 1: локально

```bash
python main.py
```

### Вариант 2: Docker

```bash
docker-compose up --build
```

## 📁 Структура

```
bot/
├── handlers/      # user, admin, payment
├── keyboards/     # user, admin, calendar
├── states/        # FSM
├── services/      # booking, payment, notify, export
├── db/            # models, crud, session
├── middlewares/   # UserMiddleware
├── filters/       # IsAdmin
├── config.py
└── scheduler.py
webhook_server.py  # aiohttp для ЮKassa
main.py
```

## 🧪 Проверка

1. Запусти бота: `python main.py`
2. Запусти ngrok: `ngrok http 8080`
3. Обнови `.env` и настройки ЮKassa
4. Открой бота → `/start` → зарегистрируйся
5. Запишись на услугу, выбери «Предоплату»
6. Перейди по ссылке ЮKassa → оплати тестовой картой
7. Получи уведомление об оплате + чек
8. Проверь `/admin` в админке

## 🐛 Возможные проблемы

**«Webhook не приходит»**
- Проверь, что ngrok запущен и URL совпадает с настройками в ЛК ЮKassa
- Проверь, что порт 8080 не занят другим процессом

**«ЮKassa create_payment error»**
- Убедись, что используешь ключи от **тестового** магазина (`test_...`)
- Проверь, что `SHOP_ID` и `SECRET_KEY` без пробелов

**«Не находит слоты»**
- Проверь настройки `WORK_START`, `WORK_END`, `LUNCH_START`, `LUNCH_END` в `.env`
- Убедись, что есть активные барберы: `SELECT * FROM barbers WHERE is_active=1;`

## 📝 Лицензия

MIT — используй как хочешь.
Что запускать
Терминал 1 — бот:

powershell
.\venv\Scripts\Activate.ps1
python main.py
Терминал 2 — FastAPI:

powershell
.\venv\Scripts\Activate.ps1
uvicorn webapp.api:app --host 0.0.0.0 --port 8000
Терминал 3 — ngrok:

powershell
.\ngrok.exe http 8000
Все три окна должны быть открыты одновременно.# Brodobrey
# Brodobrey
