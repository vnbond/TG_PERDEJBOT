# -*- coding: utf-8 -*-
# Webhook entrypoint for Render Free: Telegram sends updates to us (no long polling).
import os, asyncio
from aiohttp import web
from aiogram import Bot
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from db import init_db
from bot import dp, bot, acquire_singleton_lock

def _infer_public_url():
    # Prefer explicit WEBHOOK_URL, else construct from RENDER_EXTERNAL_URL
    url = os.environ.get("WEBHOOK_URL")
    if url:
        return url.rstrip("/")
    base = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("PUBLIC_URL")
    if base:
        return base.rstrip("/")
    # Fallback for local dev
    port = int(os.environ.get("PORT", "10000"))
    return f"http://0.0.0.0:{port}"

async def on_startup(app: web.Application):
    acquire_singleton_lock()
    init_db()

    public = _infer_public_url()
    webhook_url = public + "/webhook"
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(webhook_url)
        print("Webhook set to:", webhook_url)
    except Exception as e:
        print("Failed to set webhook:", e)

async def on_cleanup(app: web.Application):
    try:
        await bot.delete_webhook()
    except Exception:
        pass
    try:
        await bot.session.close()
    except Exception:
        pass

async def handle_root(request):
    return web.Response(text="fartbot (webhook) alive")

async def handle_health(request):
    return web.Response(text="ok")

def main():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/healthz", handle_health)

    # attach aiogram webhook handler
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    setup_application(app, webhook_handler, route="/webhook")

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    port = int(os.environ.get("PORT", "10000"))
    web.run_app(app, port=port)

if __name__ == "__main__":
    main()
