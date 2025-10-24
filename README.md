# FartBot — Telegram бот (Web Service для Render Free)

Бот считает «💨» по голосовым в группе, выдаёт ачивки и поддерживает «кнуты». 
Сборка адаптирована под **Render Web Service (Free plan)**: внутри поднимается HTTP‑сервер на `/healthz`, а Telegram‑поллинг крутится в фоне.

## Быстрый старт локально

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN=...   # токен бота
python web_entry.py    # поднимет HTTP и запустит поллинг
```

## Деплой на Render как Web Service (Free plan)

1) Залейте в GitHub. В Render: **New → Web Service → Connect repo**.
2) Runtime: **Docker**. Plan: **Free**.
3) Env Vars: 
   - `BOT_TOKEN` — вставьте токен (секрет),
   - `ADMIN_USERNAMES` — например `RussianStatham` (без `@`) или используйте `ADMIN_IDS`,
   - `PORT=10000` (для локала, Render подставит свой порт).
4) Health check: путь `/healthz`.
5) Нажмите **Deploy**. В логах увидите `fartbot alive` и `Bot started...`.
6) В @BotFather отключите **Privacy Mode** и добавьте бота в свою группу.

> ⚠️ На Free‑плане постоянных дисков нет — БД в `./data` может пропадать при пересборке. Для сохранения прогресса используйте платный план с Persistent Disk или внешнюю БД.


## Вебхуки на Render Free (рекомендуется для Free-плана)

На бесплатном плане Render боты на long polling могут «засыпать». Поэтому используйте **webhook**-режим — Telegram сам присылает события на ваш URL.

### Запуск как Web Service (Free)
1. Убедитесь, что **Dockerfile** запускает `web_entry_webhook.py` (см. ниже).
2. В Render: **New → Web Service → Connect repo** → Plan: **Free**.
3. **Environment**: 
   - `BOT_TOKEN` — токен бота (секрет)
   - `ADMIN_USERNAMES` — `RussianStatham` (или используйте `ADMIN_IDS`)
   - (опц.) `WEBHOOK_URL` — полный URL сервиса, если хотите явно задать; иначе используется `RENDER_EXTERNAL_URL`
4. **Health check path**: `/healthz`

> При старте приложение:
> - Инициализирует БД и file‑lock;
> - Ставит webhook на `<PUBLIC_URL>/webhook` (Render сам подставляет `RENDER_EXTERNAL_URL`);
> - Обрабатывает входящие апдейты через `aiogram.webhook.aiohttp_server`.

### Как переключить CMD на webhook-режим
Если вы используете мой Dockerfile из архива под polling, замените последнюю строку на:
```
CMD ["python", "-u", "web_entry_webhook.py"]
```
В архиве для webhook это уже сделано.
