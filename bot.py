# -*- coding: utf-8 -*-
import asyncio, os, re, tempfile, sys
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatType
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from db import init_db, ensure_user, add_event, get_stats, get_top, get_usernames, inc_dec_stat, log_admin_action, save_achievement, has_achievement
from audio_classifier import ogg_or_m4a_to_wav, FartClassifier
from achievements import newly_earned_achievements, ACHIEVEMENTS

load_dotenv()

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise SystemExit("Please set BOT_TOKEN in environment or .env")

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

ADMIN_IDS = set()
for s in (os.environ.get("ADMIN_IDS") or "").replace(";", ",").split(","):
    s = s.strip()
    if not s:
        continue
    try:
        ADMIN_IDS.add(int(s))
    except ValueError:
        pass

ADMIN_USERNAMES = set(u.strip().lower() for u in (os.environ.get("ADMIN_USERNAMES") or "").replace(";", ",").split(",") if u.strip())

MIN_SEC = int(os.environ.get("MIN_VOICE_SECONDS", "1"))
MAX_SEC = int(os.environ.get("MAX_VOICE_SECONDS", "12"))
CONFIDENCE_MIN = float(os.environ.get("CONFIDENCE_MIN", "0.55"))
CLASSIFIER_MODE = os.environ.get("CLASSIFIER_MODE", "heuristic")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

classifier = FartClassifier(mode=CLASSIFIER_MODE, cfg=os.environ)

LOCK_FH = None
def acquire_singleton_lock():
    global LOCK_FH
    lock_path = DATA_DIR / "instance.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FH = open(lock_path, "w")
    try:
        import fcntl
        fcntl.flock(LOCK_FH, fcntl.LOCK_EX | fcntl.LOCK_NB)
        LOCK_FH.write(str(os.getpid())) ; LOCK_FH.flush()
    except Exception:
        print("Another instance appears to be running; exiting.")
        sys.stdout.flush()
        sys.exit(0)

def is_admin(user_id: int, username: str = None) -> bool:
    uname = (username or '').lower()
    return (user_id in ADMIN_IDS) or (uname in ADMIN_USERNAMES)

def mention(user):
    if user.username:
        return f"@{user.username}"
    name = (user.first_name or '') + (' ' + user.last_name if user.last_name else '')
    return name.strip() or str(user.id)

async def resolve_target_user(message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if message.entities:
        for e in message.entities:
            if e.type == "text_mention" and e.user:
                return e.user
    if message.text:
        m = re.search(r"@([A-Za-z0-9_]{4,})", message.text)
        if m:
            pass
    return None

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        """Привет! Я считаю 💨 по голосовым.
<b>Как это работает</b>:
• Пришлите голосовое (5–6 сек) — я попробую распознать и засчитать +1.
• Выдаю ачивки (см. /achievements).
• Админы могут вручную добавлять/убирать очки и «кнуты» (/help).
""".strip()
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.reply(
        """<b>Команды</b>
/stats — ваши очки
/stats @user — очки участника
/top [7|30|0] — топ за 7/30 дней, или 0 = за всё время
/achievements — список ачивок

<b>Админ-команды</b>
/add_fart N — +N очков (в ответ на сообщение участника или с @user)
/take_fart N — -N очков
/whip N — +N кнутов
/unwhip N — -N кнутов
/set_farts N — установить точное число
""".strip()
    )

@router.message(Command("whoami"))
async def cmd_whoami(message: Message):
    u = message.from_user
    uname = f"@{u.username}" if u.username else "—"
    await message.reply(f"Ваш Telegram ID: <code>{u.id}</code>\nusername: {uname}")

@router.message(Command("achievements"))
async def cmd_ach(message: Message):
    lines = [f"{a['emoji']} <b>{a['title']}</b> — {a['threshold']} 💨" for a in ACHIEVEMENTS]
    await message.reply("\n".join(lines))

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    target = await resolve_target_user(message) or message.from_user
    ensure_user(message.chat.id, target)
    s = get_stats(message.chat.id, target.id)
    await message.reply(f"Статистика для <b>{mention(target)}</b>:\n💨: <b>{s['farts']}</b>\n🪢 кнуты: <b>{s['whips']}</b>")

@router.message(Command("top"))
async def cmd_top(message: Message, command: CommandObject):
    days = 7
    if command and command.args:
        try:
            days = int(command.args.strip())
        except Exception:
            pass
    rows = get_top(message.chat.id, days=days if days>0 else 0, limit=10)
    names = get_usernames(message.chat.id, [uid for uid,_ in rows])
    title = f"Топ по 💨 за {days} дн." if days>0 else "Топ за всё время"
    lines = [f"<b>{title}</b>"]
    for i,(uid,total) in enumerate(rows, start=1):
        lines.append(f"{i}. {names.get(uid,str(uid))}: <b>{total}</b>")
    await message.reply("\n".join(lines))

def _format_achievement_msg(user, a):
    return f"🏆 <b>{a['title']}</b> {a['emoji']} — {mention(user)} достиг {a['threshold']} 💨!"

from aiogram.types import ContentType
@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}) & (F.voice | F.audio | F.video_note))
async def on_voice(message: Message):
    dur = (message.voice and message.voice.duration) or (message.audio and message.audio.duration) or (message.video_note and message.video_note.duration) or 0
    if dur and (dur < MIN_SEC or dur > MAX_SEC):
        return
    file_id = message.voice.file_id if message.voice else (message.audio and message.audio.file_id) or (message.video_note and message.video_note.file_id)
    if not file_id:
        return

    ensure_user(message.chat.id, message.from_user)

    with tempfile.TemporaryDirectory() as td:
        ogg_path = Path(td) / "in.ogg"
        wav_path = Path(td) / "in.wav"
        try:
            try:
                await message.bot.download(file_id, destination=ogg_path)
            except Exception:
                f = await message.bot.get_file(file_id)
                await message.bot.download(f.file_path, destination=ogg_path)
            ogg_or_m4a_to_wav(str(ogg_path), str(wav_path), target_sr=32000)
        except Exception as e:
            await message.reply("Не удалось обработать голосовое: " + str(e))
            return

        res = classifier.classify(str(wav_path))

    if not res.get("is_fart") or float(res.get("score",0.0)) < CONFIDENCE_MIN:
        return

    add_event(message.chat.id, message.from_user.id, 'fart', amount=1, file_id=file_id)
    log_admin_action(message.chat.id, message.from_user.id, 'autodetect', 1, admin_user_id=None)
    s = get_stats(message.chat.id, message.from_user.id)

    old = s['farts'] - 1
    new = s['farts']
    earned = newly_earned_achievements(old, new)
    ach_msg = "\n".join(_format_achievement_msg(message.from_user, a) for a in earned if not has_achievement(message.chat.id, message.from_user.id, a['key']))
    for a in earned:
        save_achievement(message.chat.id, message.from_user.id, a['key'], a['threshold'])

    txt = f"💨 +1 для {mention(message.from_user)} (итого: <b>{s['farts']}</b>)."
    if ach_msg:
        txt += "\n\n" + ach_msg
    await message.reply(txt)

async def main():
    acquire_singleton_lock()
    init_db()
    print("Bot started. Press Ctrl+C to stop.")
    await dp.start_polling(bot, allowed_updates=["message"])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
