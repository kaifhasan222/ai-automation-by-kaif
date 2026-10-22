from __future__ import annotations

import asyncio
import logging
from difflib import get_close_matches
from html import escape

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

import uuid

from orchestrator.assets import load_assets
from orchestrator.config import ROOT, Settings, get_settings
from orchestrator.free_render import compress_for_telegram, render_free_demo, synthesize_tts
from orchestrator.openrouter_client import OpenRouterError, generate_daily_script
from orchestrator.hedra_client import create_talking_video, hedra_configured
from orchestrator.heygen_client import heygen_configured, create_avatar_video
from orchestrator.animated_reel import generate_animated_script, render_animated
from orchestrator.remotion_bridge import render_remotion_reel
from orchestrator.scene_generator import generate_scene_pack
from orchestrator.hyperframes_composer import build_hyperframes_html, render_hyperframes_mp4

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("telegram_bot")

COMMANDS: dict[str, str] = {
    "start": "Welcome + main menu",
    "help": "Saari commands + tips",
    "menu": "Keyboard buttons dikhao",
    "hyper": "Studio Photo + HyperFrames Reel",
    "script": "Free AI se reel script banao",
    "demo": "Simple face + TTS video",
    "reel": "Gemini-style Remotion reel",
    "animate": "Face-free motion reel (B-roll style cards)",
    "resend": "Last video dubara bhejo",
    "assets": "Voice / face assets check",
    "preview": "Approve / Reject review demo",
    "whoami": "Apna Telegram user id",
    "ping": "Bot alive check",
    "status": "System status",
}

# Button label -> command
BUTTON_MAP: dict[str, str] = {
    "🔥 Hyper Reel": "hyper",
    "🎬 New Script": "script",
    "✨ Gemini Reel": "reel",
    "🎞️ Animate": "animate",
    "🎥 Simple Demo": "demo",
    "🗂️ My Assets": "assets",
    "📱 Review Preview": "preview",
    "❓ Help": "help",
    "👤 Who am I": "whoami",
    "📡 Status": "status",
    "🏓 Ping": "ping",
}


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🔥 Hyper Reel"), KeyboardButton("🎬 New Script")],
            [KeyboardButton("✨ Gemini Reel"), KeyboardButton("🎞️ Animate")],
            [KeyboardButton("🎥 Simple Demo"), KeyboardButton("📱 Review Preview")],
            [KeyboardButton("🗂️ My Assets"), KeyboardButton("📡 Status")],
            [KeyboardButton("❓ Help"), KeyboardButton("🏓 Ping")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Tap 🔥 Hyper Reel or /script…",
    )


def review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve & Post", callback_data="approve"),
                InlineKeyboardButton("❌ Reject", callback_data="reject"),
            ],
            [
                InlineKeyboardButton("🔄 Regenerate", callback_data="regenerate"),
                InlineKeyboardButton("🎬 New Script", callback_data="goto_script"),
            ],
            [InlineKeyboardButton("❓ Help", callback_data="goto_help")],
        ]
    )


def suggest_commands(typo: str, n: int = 3) -> list[str]:
    keys = list(COMMANDS.keys())
    # also match without leading slash
    cleaned = typo.lstrip("/").lower().strip()
    matches = get_close_matches(cleaned, keys, n=n, cutoff=0.45)
    # common aliases
    aliases = {
        "scrpt": "script",
        "scrip": "script",
        "write": "script",
        "reel": "script",
        "animate": "animate",
        "animat": "animate",
        "video": "preview",
        "aprove": "approve",
        "aprrove": "approve",
        "hlp": "help",
        "hepl": "help",
        "menue": "menu",
        "stat": "status",
        "id": "whoami",
        "me": "whoami",
    }
    if cleaned in aliases and aliases[cleaned] not in matches:
        matches.insert(0, aliases[cleaned])
    return matches[:n]


def _deny_text(settings: Settings, user_id: int) -> str | None:
    if settings.telegram_allowed_user_ids and user_id not in settings.telegram_allowed_user_ids:
        return (
            f"🔒 Access denied for user <code>{user_id}</code>.\n"
            "Apna id <code>TELEGRAM_ALLOWED_USER_IDS</code> mein add karo."
        )
    return None


async def _guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if allowed to continue."""
    settings: Settings = context.bot_data["settings"]
    user = update.effective_user
    if not user:
        return False
    deny = _deny_text(settings, user.id)
    if not deny:
        return True
    if update.callback_query:
        await update.callback_query.answer("Access denied", show_alert=True)
    elif update.message:
        await update.message.reply_text(deny, parse_mode=ParseMode.HTML)
    return False


async def _typing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat:
        await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)


async def _typing_loop(update: Update, context: ContextTypes.DEFAULT_TYPE, stop: asyncio.Event) -> None:
    """Keep the 'typing…' bubble alive while a long job runs."""
    while not stop.is_set():
        try:
            await _typing(update, context)
        except Exception:  # noqa: BLE001
            return
        try:
            await asyncio.wait_for(stop.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            continue


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context) or not update.message:
        return
    settings: Settings = context.bot_data["settings"]
    name = escape(update.effective_user.first_name or "creator") if update.effective_user else "creator"

    lock = (
        "⚠️ Allow-list empty — kisi ko bhi access mil sakta hai. /whoami chalao."
        if not settings.telegram_allowed_user_ids
        else "✅ Secure: sirf tumhare Telegram id pe locked."
    )

    await update.message.reply_text(
        f"👋 Hey <b>{name}</b>!\n\n"
        "Main tumhara <b>Daily AI Reels</b> assistant hoon.\n"
        f"{lock}\n\n"
        "Neeche buttons se start karo — ya type karo <code>/script</code>.\n"
        "Galat command likhoge toh main suggestion dunga ✨",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context) or not update.message:
        return
    lines = ["🆘 <b>Help — commands</b>\n"]
    for name, desc in COMMANDS.items():
        lines.append(f"• /{name} — {escape(desc)}")
    lines.append(
        "\n💡 <b>Tips</b>\n"
        "• <code>/script AI agents</code> — topic hint ke saath\n"
        "• Buttons bhi same kaam karte hain\n"
        "• Typo? e.g. <code>/scrpt</code> → main /script suggest karunga"
    )
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context) or not update.message:
        return
    await update.message.reply_text(
        "🎛️ Menu ready — button dabao:",
        reply_markup=main_keyboard(),
    )


async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    # whoami always allowed so user can recover access
    user = update.effective_user
    await update.message.reply_text(
        "👤 <b>Your Telegram profile</b>\n\n"
        f"ID: <code>{user.id}</code>\n"
        f"Username: @{escape(user.username or '—')}\n"
        f"Name: {escape(user.first_name or '')}",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context) or not update.message:
        return
    await _typing(update, context)
    await asyncio.sleep(0.35)
    await update.message.reply_text("pong ✅ Bot online hai.", reply_markup=main_keyboard())


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context) or not update.message:
        return
    settings: Settings = context.bot_data["settings"]
    await _typing(update, context)
    has_or = bool(settings.openrouter_api_key)
    locked = bool(settings.telegram_allowed_user_ids)
    assets = load_assets()
    await update.message.reply_text(
        "📡 <b>System status</b>\n\n"
        f"• Telegram bot: ✅ online\n"
        f"• OpenRouter key: {'✅ set' if has_or else '❌ missing'}\n"
        f"• Hedra avatar: {'✅ photo lip-sync' if __import__('os').getenv('HEDRA_API_KEY') else '❌ missing'}\n"
        f"• HeyGen: {'wallet $0' if __import__('os').getenv('HEYGEN_API_KEY') else '❌'}\n"
        f"• Model: <code>{escape(settings.openrouter_model)}</code>\n"
        f"• Niche: {escape(settings.content_niche)}\n"
        f"• Language: {escape(settings.content_language)}\n"
        f"• Access lock: {'✅ on' if locked else '⚠️ off'}\n"
        f"• Face/voice assets: {'✅ ready' if not assets.missing() else '⚠️ incomplete'}\n"
        f"• Free demo video: ✅ /demo\n"
        f"• Voice-clone lip-sync GPU: ⏳ Modal next\n"
        f"• YT / IG publish: ⏳ later",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


async def cmd_assets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context) or not update.message:
        return
    await _typing(update, context)
    assets = load_assets()
    await update.message.reply_text(
        assets.summary_html(),
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )
    # Send photo preview if present
    if assets.avatar_photo.exists():
        try:
            with assets.avatar_photo.open("rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption="📸 Avatar photo loaded",
                )
        except Exception:  # noqa: BLE001
            log.exception("photo preview failed")


async def cmd_animate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Script + motion cards + SFX. No face, no voice clone."""
    if not await _guard(update, context) or not update.message:
        return
    settings: Settings = context.bot_data["settings"]
    topic = " ".join(context.args).strip() if context.args else settings.content_niche
    status = await update.message.reply_text(
        "🎞️ <b>Animated reel</b>\nScript → motion cards → SFX\n<i>Face / avatar nahi</i>",
        parse_mode=ParseMode.HTML,
    )
    stop = asyncio.Event()
    typer = asyncio.create_task(_typing_loop(update, context, stop))
    try:
        data = await generate_animated_script(settings, topic)
        title = str(data.get("title") or topic)
        await status.edit_text(
            f"✍️ <b>{escape(title)}</b>\n🎬 Render…",
            parse_mode=ParseMode.HTML,
        )
        video_path = await asyncio.to_thread(render_animated, data, title)
        context.bot_data["last_video_path"] = str(video_path)
    except Exception as exc:  # noqa: BLE001
        stop.set()
        await typer
        await status.edit_text(
            f"⚠️ Animate fail:\n<code>{escape(str(exc)[:500])}</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    stop.set()
    await typer
    caption = str(data.get("caption") or title)
    await _send_video_resilient(
        update,
        context,
        video_path,
        caption=f"🎞️ {title}\n\n{caption}"[:900],
        reply_markup=review_keyboard(),
    )
    await status.edit_text("✅ Animated reel ready.", parse_mode=ParseMode.HTML)


async def cmd_hyper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Zero-Cost Studio Photo + HyperFrames Reel generator."""
    if not await _guard(update, context) or not update.message:
        return
    settings: Settings = context.bot_data["settings"]
    hint = " ".join(context.args).strip() if context.args else None

    status = await update.message.reply_text(
        "🔥 <b>HyperFrames Studio Reel</b>\n"
        "1️⃣ AI Script Research\n"
        "2️⃣ Studio Avatar clips (kaif_tech_news_set.jpg)\n"
        "3️⃣ Motion Cards + Mesh Glow + SFX\n"
        "<i>Zero-cost processing…</i>",
        parse_mode=ParseMode.HTML,
    )
    stop = asyncio.Event()
    typer = asyncio.create_task(_typing_loop(update, context, stop))
    try:
        topic = hint or settings.content_niche
        data = await generate_animated_script(settings, topic)
        title = str(data.get("title") or topic)
        scenes = data.get("scenes") or []
        if len(scenes) < 3:
            raise RuntimeError("Script missing scenes")

        await status.edit_text(
            f"✍️ <b>{escape(title)}</b>\n📸 Generating Studio Avatar Clips…",
            parse_mode=ParseMode.HTML,
        )

        job_id = uuid.uuid4().hex[:8]
        work_dir = ROOT / "outputs" / f"hyper_{job_id}"
        clips = await generate_scene_pack(scenes, work_dir)

        await status.edit_text(
            f"🎬 <b>{escape(title)}</b>\n✨ HyperFrames Motion & SFX Rendering…",
            parse_mode=ParseMode.HTML,
        )

        html_file = work_dir / "index.html"
        build_hyperframes_html(clips=clips, title=title, kicker="NEW KAIF AI", out_html=html_file)

        output_mp4 = work_dir / "kaif_reel.mp4"
        await asyncio.to_thread(render_hyperframes_mp4, clips=clips, output_mp4=output_mp4, title=title)

        context.bot_data["last_video_path"] = str(output_mp4)
        stop.set()
        await typer

        caption = (
            f"🔥 <b>{escape(title)}</b>\n\n"
            f"📸 Studio Avatar: kaif_tech_news_set.jpg\n"
            f"⚡ Engine: HyperFrames + Kinetic Cards + SFX\n\n"
            f"{escape(str(data.get('caption') or ''))}"
        )[:950]

        await _send_video_resilient(
            update,
            context,
            output_mp4,
            caption=caption,
            reply_markup=review_keyboard(),
        )
        await status.edit_text("✅ HyperFrames Reel ready!", parse_mode=ParseMode.HTML)
    except Exception as exc:
        stop.set()
        await typer
        log.exception("cmd_hyper failed")
        await status.edit_text(
            f"❌ Hyper Reel fail:\n<code>{escape(str(exc)[:600])}</code>",
            parse_mode=ParseMode.HTML,
        )


async def cmd_reel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gemini-style Remotion: captions + motion + SFX + face + TTS."""
    if not await _guard(update, context) or not update.message:
        return
    settings: Settings = context.bot_data["settings"]
    assets = load_assets()
    if assets.missing():
        await update.message.reply_text(
            f"⚠️ Assets missing: {', '.join(assets.missing())}",
            reply_markup=main_keyboard(),
        )
        return

    hint = " ".join(context.args) if context.args else None
    use_hedra = hedra_configured()
    use_heygen = heygen_configured() and not use_hedra
    status = await update.message.reply_text(
        (
            "✨ <b>Hedra talking photo…</b>\n"
            "1) Script (OpenRouter)\n"
            "2) Voice\n"
            "3) Tumhari photo se lip-sync video\n"
            "<i>2–4 min · 540p</i>"
            if use_hedra
            else (
                "✨ <b>HeyGen avatar reel…</b>\n1) Script\n2) HeyGen avatar"
                if use_heygen
                else "✨ <b>Remotion reel…</b>\nCaptions + motion + SFX"
            )
        ),
        parse_mode=ParseMode.HTML,
    )

    stop = asyncio.Event()
    typer = asyncio.create_task(_typing_loop(update, context, stop))
    try:
        data = await generate_daily_script(settings, topic_hint=hint)
        script = str(data.get("script") or "").strip()
        title = str(data.get("title") or "AI Kaif reel")
        hook = str(data.get("hook") or title)
        if not script:
            raise RuntimeError("Empty script")

        engine = "Hedra" if use_hedra else "HeyGen" if use_heygen else "Remotion"
        await status.edit_text(
            f"✍️ <b>{escape(title)}</b>\n🎬 {engine} render…",
            parse_mode=ParseMode.HTML,
        )
        if update.effective_chat:
            await context.bot.send_chat_action(
                update.effective_chat.id, ChatAction.UPLOAD_VIDEO
            )

        if use_hedra:
            spoken = script[:420]
            audio_path = ROOT / "outputs" / "hedra_voice.mp3"
            await synthesize_tts(spoken, audio_path)
            video_path = await create_talking_video(
                image=load_assets().avatar_photo,
                audio=audio_path,
                title=title,
                prompt=hook[:180] or "Speaking naturally to camera",
            )
        elif use_heygen:
            video_path = await create_avatar_video(script, title=title)
        else:
            video_path = await render_remotion_reel(
                script=script,
                hook=hook[:80],
                title=title,
                brand="AI Kaif",
            )
    except OpenRouterError as exc:
        stop.set()
        await typer
        await status.edit_text(
            f"⚠️ OpenRouter:\n<code>{escape(str(exc)[:500])}</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    except Exception as exc:  # noqa: BLE001
        stop.set()
        await typer
        log.exception("reel failed")
        await status.edit_text(
            f"❌ Reel fail:\n<code>{escape(str(exc)[:700])}</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    finally:
        stop.set()
        if not typer.done():
            await typer

    context.bot_data["last_video_path"] = str(video_path)
    caption = (
        f"✨ <b>{escape(title)}</b>\n\n"
        + (
            "Hedra: tumhari photo + lip-sync (540p)."
            if use_hedra
            else "HeyGen avatar."
            if use_heygen
            else "Remotion: captions + motion + SFX."
        )
    )
    await status.edit_text("✅ Reel ready — upload…")
    await _send_video_resilient(
        update,
        context,
        video_path,
        caption=caption,
        reply_markup=review_keyboard(),
    )


async def cmd_demo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Free path: OpenRouter script (optional) + Edge TTS + your face video."""
    if not await _guard(update, context) or not update.message:
        return
    settings: Settings = context.bot_data["settings"]
    assets = load_assets()
    if assets.missing():
        await update.message.reply_text(
            f"⚠️ Assets missing: {', '.join(assets.missing())}\nPehle /assets check karo.",
            reply_markup=main_keyboard(),
        )
        return

    hint = " ".join(context.args) if context.args else None
    status = await update.message.reply_text(
        "🎥 <b>Simple demo (no Remotion)…</b>\n"
        "1) Script (OpenRouter free)\n"
        "2) Voice (TTS)\n"
        "3) Face video + audio mux\n"
        "<i>Gemini style ke liye /reel use karo</i>",
        parse_mode=ParseMode.HTML,
    )

    stop = asyncio.Event()
    typer = asyncio.create_task(_typing_loop(update, context, stop))

    try:
        data = await generate_daily_script(settings, topic_hint=hint)
        script = str(data.get("script") or "").strip()
        title = str(data.get("title") or "Kaif demo")
        if not script:
            raise RuntimeError("Empty script from OpenRouter")

        await status.edit_text(
            f"✍️ Script ready: <b>{escape(title)}</b>\n"
            "🔊 TTS + video mux chal raha hai…",
            parse_mode=ParseMode.HTML,
        )
        # Upload action while rendering / sending
        if update.effective_chat:
            await context.bot.send_chat_action(
                update.effective_chat.id, ChatAction.UPLOAD_VIDEO
            )

        video_path = await render_free_demo(script, title=title)
    except OpenRouterError as exc:
        stop.set()
        await typer
        await status.edit_text(
            f"⚠️ OpenRouter error:\n<code>{escape(str(exc)[:500])}</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    except Exception as exc:  # noqa: BLE001
        stop.set()
        await typer
        log.exception("demo failed")
        await status.edit_text(
            f"❌ Demo failed:\n<code>{escape(str(exc)[:500])}</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    finally:
        stop.set()
        if not typer.done():
            await typer

    caption = (
        f"🎬 <b>{escape(title)}</b>\n\n"
        "⚠️ Free demo: face video tumhara hai, voice abhi macOS TTS hai "
        "(clone + lip-sync Modal pe aayega).\n\n"
        "Review:"
    )
    context.bot_data["last_video_path"] = str(video_path)
    await status.edit_text(
        f"✅ Video ready ({video_path.stat().st_size / 1024 / 1024:.1f} MB) — upload…\n"
        "<i>Agar timeout ho toh /resend dabao</i>",
        parse_mode=ParseMode.HTML,
    )
    ok = await _send_video_resilient(
        update,
        context,
        video_path,
        caption=caption,
        reply_markup=review_keyboard(),
    )
    if ok:
        try:
            await status.edit_text("✅ Video bhej diya!")
        except BadRequest:
            pass


async def _send_video_resilient(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    video_path,
    *,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Upload with long timeout; compress + document fallback on failure."""
    from pathlib import Path

    path = Path(video_path)
    if not path.exists():
        if update.message:
            await update.message.reply_text("Video file missing.")
        return False

    chat = update.effective_chat
    if chat:
        await context.bot.send_chat_action(chat.id, ChatAction.UPLOAD_VIDEO)

    # If still large, compress first
    send_path = path
    if path.stat().st_size > 12 * 1024 * 1024:
        if update.message:
            await update.message.reply_text(
                f"📦 {path.stat().st_size / 1024 / 1024:.1f} MB — Telegram ke liye compress…"
            )
        try:
            send_path = await asyncio.to_thread(
                compress_for_telegram, path, path.with_name(path.stem + "_tg.mp4")
            )
            context.bot_data["last_video_path"] = str(send_path)
        except Exception as exc:  # noqa: BLE001
            log.exception("compress failed")
            if update.message:
                await update.message.reply_text(f"Compress fail: {exc}")

    async def _try_video(p) -> None:
        with p.open("rb") as vid:
            await update.message.reply_video(
                video=vid,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                supports_streaming=True,
                read_timeout=300,
                write_timeout=300,
                connect_timeout=60,
                pool_timeout=60,
            )

    async def _try_doc(p) -> None:
        with p.open("rb") as vid:
            await update.message.reply_document(
                document=vid,
                filename=p.name,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                read_timeout=300,
                write_timeout=300,
                connect_timeout=60,
                pool_timeout=60,
            )

    if not update.message:
        return False

    try:
        await _try_video(send_path)
        return True
    except Exception as exc1:  # noqa: BLE001
        log.warning("reply_video failed: %s — trying document", exc1)

    try:
        await _try_doc(send_path)
        return True
    except Exception as exc2:  # noqa: BLE001
        log.exception("document send failed")
        await update.message.reply_text(
            f"Upload fail: {escape(str(exc2)[:250])}\n"
            f"File Mac pe hai: <code>{escape(str(send_path))}</code>\n"
            "Phir se /resend try karo.",
            parse_mode=ParseMode.HTML,
        )
        return False


async def cmd_resend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context) or not update.message:
        return
    from pathlib import Path

    raw = context.bot_data.get("last_video_path")
    path = Path(raw) if raw else None
    if not path or not path.exists():
        # fallback: newest mp4 under outputs/
        outs = sorted((ROOT / "outputs").rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        # prefer *_tg.mp4 then newest
        tg = [p for p in outs if p.name.endswith("_tg.mp4")]
        path = (tg[0] if tg else outs[0]) if outs else None

    if not path or not path.exists():
        await update.message.reply_text("Koi last video nahi mili. Pehle /demo chalao.")
        return

    await update.message.reply_text(
        f"📤 Resend: <code>{escape(path.name)}</code> ({path.stat().st_size/1024/1024:.1f} MB)",
        parse_mode=ParseMode.HTML,
    )
    await _send_video_resilient(
        update,
        context,
        path,
        caption="🎬 Resent video",
        reply_markup=review_keyboard(),
    )


async def cmd_script(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context) or not update.message:
        return
    settings: Settings = context.bot_data["settings"]
    hint = " ".join(context.args) if context.args else None

    status = await update.message.reply_text(
        "✍️ <b>Script likh raha hoon…</b>\n"
        "<i>OpenRouter free model · 5–20 sec</i>",
        parse_mode=ParseMode.HTML,
    )

    stop = asyncio.Event()
    typer = asyncio.create_task(_typing_loop(update, context, stop))

    try:
        data = await generate_daily_script(settings, topic_hint=hint)
    except OpenRouterError as exc:
        stop.set()
        await typer
        await status.edit_text(
            "⚠️ <b>OpenRouter error</b>\n\n"
            f"<code>{escape(str(exc)[:500])}</code>\n\n"
            "Key check karo: https://openrouter.ai/keys",
            parse_mode=ParseMode.HTML,
        )
        return
    except Exception as exc:  # noqa: BLE001
        stop.set()
        await typer
        log.exception("script failed")
        await status.edit_text(f"❌ Failed: {escape(str(exc)[:400])}", parse_mode=ParseMode.HTML)
        return
    finally:
        stop.set()
        if not typer.done():
            await typer

    title = escape(str(data.get("title", "Untitled")))
    hook = escape(str(data.get("hook", "")))
    script = escape(str(data.get("script", ""))[:2800])
    caption = escape(str(data.get("caption", ""))[:700])

    text = (
        f"🎬 <b>{title}</b>\n\n"
        f"🪝 <b>Hook</b>\n{hook}\n\n"
        f"🎙️ <b>Script</b>\n{script}\n\n"
        f"📝 <b>Caption</b>\n{caption}"
    )
    try:
        await status.edit_text(text, parse_mode=ParseMode.HTML)
    except BadRequest:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    await update.message.reply_text(
        "Next: review gate try karo 👇",
        reply_markup=review_keyboard(),
    )


async def cmd_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context) or not update.message:
        return
    await _typing(update, context)
    await update.message.reply_text(
        "📱 <b>Review gate</b>\n\n"
        "Jab daily video ready hogi, yahi card aayega.\n"
        "Abhi demo mode — publish baad mein connect hoga.",
        parse_mode=ParseMode.HTML,
        reply_markup=review_keyboard(),
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.from_user:
        return
    if not await _guard(update, context):
        return

    action = query.data or ""
    await query.answer()

    if action == "goto_script":
        await query.edit_message_text("🎬 Script ke liye /script bhejo ya button dabao.")
        if update.effective_chat:
            # simulate by sending a nudge with keyboard
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Topic likho ya seedha /script dabao.",
                reply_markup=main_keyboard(),
            )
        return

    if action == "goto_help":
        await query.edit_message_text("Help khol raha hoon…")
        # reuse help content via a fake message path — send help text
        if update.effective_chat:
            fake = update
            # send help as new message
            lines = ["🆘 <b>Help — commands</b>\n"]
            for name, desc in COMMANDS.items():
                lines.append(f"• /{name} — {escape(desc)}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=main_keyboard(),
            )
        return

    if action == "regenerate":
        await query.answer("Regenerating…", show_alert=False)
        await query.edit_message_text(
            "🔄 <b>Regenerate</b>\n\n"
            "Naya script chahiye? Neeche /script bhejo.\n"
            "<i>(Full video regenerate pipeline next phase.)</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    labels = {
        "approve": (
            "✅ <b>Approved</b>\n\n"
            "Publish step abhi wire nahi hua — free MVP.\n"
            "Jab YT/IG connect hoga, yahi button post karega."
        ),
        "reject": (
            "❌ <b>Rejected</b>\n\n"
            "Theek hai. Naya try: /script ya 🎬 New Script."
        ),
    }
    text = labels.get(action, f"Got: {escape(action)}")
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)


async def on_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not await _guard(update, context):
        return

    raw = update.message.text.strip()
    cmd = raw.split()[0].split("@")[0]
    suggestions = suggest_commands(cmd)

    await _typing(update, context)

    if suggestions:
        buttons = [
            [InlineKeyboardButton(f"/{s}", callback_data=f"suggest_{s}")]
            for s in suggestions
        ]
        buttons.append([InlineKeyboardButton("❓ Help", callback_data="goto_help")])
        await update.message.reply_text(
            f"🤔 <code>{escape(cmd)}</code> samajh nahi aaya.\n\n"
            "Kya yeh meant kar rahe the?",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    await update.message.reply_text(
        f"🤷 Command <code>{escape(cmd)}</code> nahi mili.\n"
        "Try /help ya neeche wale buttons.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


async def on_suggest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("suggest_"):
        return
    if not await _guard(update, context):
        return

    cmd = query.data.removeprefix("suggest_")
    await query.answer(f"Running /{cmd}")
    await query.edit_message_text(f"▶️ Running <b>/{escape(cmd)}</b>…", parse_mode=ParseMode.HTML)

    # Dispatch known commands by synthesizing text — call handlers directly
    handlers = {
        "start": cmd_start,
        "help": cmd_help,
        "menu": cmd_menu,
        "script": cmd_script,
        "preview": cmd_preview,
        "whoami": cmd_whoami,
        "ping": cmd_ping,
        "status": cmd_status,
    }
    handler = handlers.get(cmd)
    if not handler or not update.effective_chat:
        return

    # Create a minimal message so handlers can reply
    # Easiest path: send a temporary instruction and invoke via bot commands UX
    msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"/{cmd}",
        reply_markup=main_keyboard(),
    )
    # Build a shallow update-like flow: call handler with a cloned update is hard.
    # Instead map to direct calls by patching update.message
    update._message = msg  # type: ignore[attr-defined]
    # telegram Update is frozen-ish; safer to call handler functions with new send
    if cmd == "script":
        context.args = []
        # Fabricate by sending status on this message path
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        await cmd_script_from_chat(update.effective_chat.id, context)
    elif cmd == "preview":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "📱 <b>Review gate</b>\n\n"
                "Jab daily video ready hogi, yahi card aayega.\n"
                "Abhi demo mode — publish baad mein connect hoga."
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=review_keyboard(),
        )
    elif cmd == "help":
        lines = ["🆘 <b>Help — commands</b>\n"]
        for name, desc in COMMANDS.items():
            lines.append(f"• /{name} — {escape(desc)}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(),
        )
    elif cmd == "status":
        settings: Settings = context.bot_data["settings"]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "📡 <b>System status</b>\n\n"
                f"• OpenRouter: {'✅' if settings.openrouter_api_key else '❌'}\n"
                f"• Model: <code>{escape(settings.openrouter_model)}</code>\n"
                f"• Niche: {escape(settings.content_niche)}"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(),
        )
    elif cmd == "whoami":
        user = query.from_user
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"👤 ID: <code>{user.id}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(),
        )
    elif cmd == "ping":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="pong ✅",
            reply_markup=main_keyboard(),
        )
    elif cmd == "menu":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🎛️ Menu:",
            reply_markup=main_keyboard(),
        )
    elif cmd == "start":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="👋 Menu ready — button dabao.",
            reply_markup=main_keyboard(),
        )


async def cmd_script_from_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    status = await context.bot.send_message(
        chat_id=chat_id,
        text="✍️ <b>Script likh raha hoon…</b>",
        parse_mode=ParseMode.HTML,
    )
    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
    try:
        data = await generate_daily_script(settings, topic_hint=None)
    except Exception as exc:  # noqa: BLE001
        await status.edit_text(f"❌ {escape(str(exc)[:400])}", parse_mode=ParseMode.HTML)
        return

    title = escape(str(data.get("title", "Untitled")))
    hook = escape(str(data.get("hook", "")))
    script = escape(str(data.get("script", ""))[:2800])
    caption = escape(str(data.get("caption", ""))[:700])
    await status.edit_text(
        f"🎬 <b>{title}</b>\n\n🪝 <b>Hook</b>\n{hook}\n\n"
        f"🎙️ <b>Script</b>\n{script}\n\n📝 <b>Caption</b>\n{caption}",
        parse_mode=ParseMode.HTML,
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply keyboard buttons + free text with smart suggestions."""
    if not update.message or not update.message.text:
        return
    if not await _guard(update, context):
        return

    text = update.message.text.strip()

    # Reply keyboard button
    if text in BUTTON_MAP:
        cmd = BUTTON_MAP[text]
        context.args = []
        dispatch = {
            "script": cmd_script,
            "reel": cmd_reel,
            "animate": cmd_animate,
            "demo": cmd_demo,
            "resend": cmd_resend,
            "assets": cmd_assets,
            "preview": cmd_preview,
            "help": cmd_help,
            "whoami": cmd_whoami,
            "status": cmd_status,
            "ping": cmd_ping,
        }
        handler = dispatch.get(cmd)
        if handler:
            await handler(update, context)
        return

    # Looks like a mistyped slash command without being caught
    if text.startswith("/"):
        await on_unknown_command(update, context)
        return

    # Natural language: treat as script topic if long enough, else suggest
    await _typing(update, context)
    lower = text.lower()

    if any(w in lower for w in ("script", "reel", "video", "topic", "banao", "likho")):
        context.args = [text]
        await cmd_script(update, context)
        return

    suggestions = suggest_commands(text)
    if suggestions:
        buttons = [[InlineKeyboardButton(f"/{s} — {COMMANDS[s]}", callback_data=f"suggest_{s}")] for s in suggestions]
        buttons.append(
            [InlineKeyboardButton("🎬 Use this as script topic", callback_data=f"topic::{text[:60]}")]
        )
        await update.message.reply_text(
            f"🙂 Samajh gaya almost — <i>{escape(text[:120])}</i>\n\n"
            "Kya karna chahte ho?",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    # Default: offer to generate script from free text as topic
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎬 Is topic pe script banao", callback_data=f"topic::{text[:80]}")],
            [InlineKeyboardButton("❓ Help", callback_data="goto_help")],
        ]
    )
    await update.message.reply_text(
        "💬 Message mil gaya.\n\n"
        "Agar yeh topic hai toh button dabao — warna /help dekho.",
        reply_markup=keyboard,
    )


async def on_topic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("topic::"):
        return
    if not await _guard(update, context):
        return
    topic = query.data.removeprefix("topic::")
    await query.answer("Script bana raha hoon…")
    await query.edit_message_text(
        f"✍️ Topic: <b>{escape(topic)}</b>\nScript aa rahi hai…",
        parse_mode=ParseMode.HTML,
    )
    if update.effective_chat:
        settings: Settings = context.bot_data["settings"]
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        stop = asyncio.Event()

        async def _loop() -> None:
            while not stop.is_set():
                await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=4.0)
                except asyncio.TimeoutError:
                    continue

        typer = asyncio.create_task(_loop())
        try:
            data = await generate_daily_script(settings, topic_hint=topic)
        except Exception as exc:  # noqa: BLE001
            stop.set()
            await typer
            await context.bot.send_message(
                update.effective_chat.id,
                f"❌ {escape(str(exc)[:400])}",
                parse_mode=ParseMode.HTML,
            )
            return
        finally:
            stop.set()
            if not typer.done():
                await typer

        title = escape(str(data.get("title", "Untitled")))
        hook = escape(str(data.get("hook", "")))
        script = escape(str(data.get("script", ""))[:2800])
        caption = escape(str(data.get("caption", ""))[:700])
        await context.bot.send_message(
            update.effective_chat.id,
            f"🎬 <b>{title}</b>\n\n🪝 <b>Hook</b>\n{hook}\n\n"
            f"🎙️ <b>Script</b>\n{script}\n\n📝 <b>Caption</b>\n{caption}",
            parse_mode=ParseMode.HTML,
            reply_markup=review_keyboard(),
        )


async def on_post_init(app: Application) -> None:
    await app.bot.set_my_commands(
        [BotCommand(name, desc) for name, desc in COMMANDS.items()]
    )
    log.info("Bot commands menu registered")


def build_app(settings: Settings | None = None) -> Application:
    settings = settings or get_settings()
    # Long timeouts so ~10–25MB video uploads don't die at default ~20s
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=60.0,
        read_timeout=300.0,
        write_timeout=300.0,
        pool_timeout=60.0,
    )
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .request(request)
        .get_updates_request(request)
        .post_init(on_post_init)
        .build()
    )
    app.bot_data["settings"] = settings

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("whoami", cmd_whoami))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("script", cmd_script))
    app.add_handler(CommandHandler("demo", cmd_demo))
    app.add_handler(CommandHandler("hyper", cmd_hyper))
    app.add_handler(CommandHandler("reel", cmd_reel))
    app.add_handler(CommandHandler("animate", cmd_animate))
    app.add_handler(CommandHandler("resend", cmd_resend))
    app.add_handler(CommandHandler("assets", cmd_assets))
    app.add_handler(CommandHandler("preview", cmd_preview))

    app.add_handler(CallbackQueryHandler(on_suggest_callback, pattern=r"^suggest_"))
    app.add_handler(CallbackQueryHandler(on_topic_callback, pattern=r"^topic::"))
    app.add_handler(CallbackQueryHandler(on_callback))

    # Unknown /commands
    app.add_handler(MessageHandler(filters.COMMAND, on_unknown_command))
    # Buttons + free text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    return app


def main() -> None:
    settings = get_settings()
    log.info("Starting Telegram bot (allowed=%s)", settings.telegram_allowed_user_ids or "ALL")
    app = build_app(settings)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
