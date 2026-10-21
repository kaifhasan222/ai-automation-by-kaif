# AI Video Automation (Free-first)

MacBook Air + Telegram + OpenRouter. Heavy voice/avatar GPU later on Modal/RunPod.

## What works now (₹0)

- Telegram bot: `/start` `/whoami` `/script` `/preview` `/demo` `/reel`
- OpenRouter script generation (free model router)
- Remotion Gemini-style template (captions + motion + SFX)
- Studio: `cd editor_engine/remotion_template && npm run studio`

## Not free / needs cloud GPU (later)

- Open-source voice clone (GPT-SoVITS / CosyVoice)
- Lip-sync avatar (MuseTalk / LatentSync)
- YouTube + Instagram auto-publish (API setup)

## Setup

```bash
cd /Users/kaifhasan/Movies/ai-video-automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install once (Homebrew):

```bash
brew install ffmpeg
```

Copy env:

```bash
cp .env.example .env
# fill TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY, TELEGRAM_ALLOWED_USER_IDS
```

### OpenRouter key (important)

Use a **normal API key** from [openrouter.ai/keys](https://openrouter.ai/keys).

A **management key** from [management-keys](https://openrouter.ai/settings/management-keys) **cannot** call models.

Recommended free model in `.env`:

```env
OPENROUTER_MODEL=openrouter/free
```

### Run bot

```bash
source .venv/bin/activate
python scripts/run_bot.py
```

Telegram pe `@new_kaif_ai_bot` → `/start` → `/whoami` → id `.env` mein daalo → bot restart.

## Security

Never commit `.env`. If a token was pasted in chat, revoke + regenerate it.