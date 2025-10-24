# -*- coding: utf-8 -*-
# Web Service entrypoint for Render Free plan: exposes HTTP port and runs Telegram bot polling in background.
import os, asyncio
from aiohttp import web

from db import init_db
from bot import dp, bot, acquire_singleton_lock

async def start_polling(app: web.Application):
    acquire_singleton_lock()
    init_db()
    app['poller'] = asyncio.create_task(dp.start_polling(bot, allowed_updates=["message"]))

async def stop_polling(app: web.Application):
    task = app.get('poller')
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    try:
        await bot.session.close()
    except Exception:
        pass

async def handle_root(request):
    return web.Response(text="fartbot alive")

async def handle_health(request):
    return web.Response(text="ok")

def main():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/healthz", handle_health)
    app.on_startup.append(start_polling)
    app.on_cleanup.append(stop_polling)

    port = int(os.environ.get("PORT", "10000"))
    web.run_app(app, port=port)

if __name__ == "__main__":
    main()
