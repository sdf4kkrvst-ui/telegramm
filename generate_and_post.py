#!/usr/bin/env python3
"""Generate a fresh, original post via the Anthropic API and publish it to
Telegram. Falls back (via non-zero exit) to the bank-based post.py if
anything goes wrong — see the workflow's `run:` step.

Requires env vars:
  ANTHROPIC_API_KEY
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHANNEL   (defaults to @allbegoods)
"""
import json
import os
import random
import re
import sys
import urllib.parse
import urllib.request

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@allbegoods")

# Pre-vetted free (Unsplash License) photos, one per topical category.
PHOTO_POOL = {
    "space": ["https://images.unsplash.com/photo-1631673563189-d7ef75a1247e?fm=jpg&q=70&w=1280&auto=format&fit=crop"],
    "food": ["https://images.unsplash.com/photo-1617228069096-4638a7ffc906?fm=jpg&q=70&w=1280&auto=format&fit=crop"],
    "tech": ["https://images.unsplash.com/photo-1634947096506-6d9f114cf64e?fm=jpg&q=70&w=1280&auto=format&fit=crop"],
    "nature": ["https://images.unsplash.com/photo-1768808520785-a4ce8c12c335?fm=jpg&q=70&w=1280&auto=format&fit=crop"],
    "animals": ["https://images.unsplash.com/photo-1563551937069-caa966ba3aa8?fm=jpg&q=70&w=1280&auto=format&fit=crop"],
    "history": ["https://images.unsplash.com/photo-1775229106888-dca42d0c9f4f?fm=jpg&q=70&w=1280&auto=format&fit=crop"],
    "sport": ["https://images.unsplash.com/photo-1461896836934-ffe607ba8211?fm=jpg&q=70&w=1280&auto=format&fit=crop"],
    "science": ["https://images.unsplash.com/photo-1758206523826-a65d4cf070aa?fm=jpg&q=70&w=1280&auto=format&fit=crop"],
    "psychology": ["https://images.unsplash.com/photo-1559757296-c68c34d39551?fm=jpg&q=70&w=1280&auto=format&fit=crop"],
    "humor": ["https://images.unsplash.com/photo-1582298538104-fe2e74c27f59?fm=jpg&q=70&w=1280&auto=format&fit=crop"],
}

SYSTEM_PROMPT = """Ты помогаешь вести Telegram-канал @allbegoods — общая тематика "всякая всячина" (новости, факты, юмор, разное) для русскоязычной аудитории в России.

Сгенерируй ОДИН пост. Ответь СТРОГО в виде JSON-объекта, без markdown-обрамления и пояснений до/после, в формате:
{"text": "текст поста на русском, 2-5 предложений, с одним уместным эмодзи в начале", "category": "space", "use_photo": true}

Правила:
1. category должна быть одной из: space, science, history, nature, animals, food, tech, sport, psychology, humor.
2. use_photo: true можно ставить для любой из этих категорий, если тема достаточно общая, чтобы иллюстрироваться нейтральной фотографией (не конкретное свежее событие).
3. Текст — ОРИГИНАЛЬНЫЙ, своими словами. НЕ копируй дословно ничьи тексты. Если нужна цитата — короче 15 слов, с указанием источника.
4. КРИТИЧНО — соответствие законодательству РФ: категорически ИЗБЕГАЙ тем: политика и предвыборная агитация; военные действия/спецоперация и любая позиция по ним; критика властей/армии/госсимволики; ЛГБТ в любом контексте; оскорбление религиозных чувств; пропаганда наркотиков/экстремизма/терроризма; иностранные агенты/нежелательные организации. При малейшем сомнении в теме — выбери другую, однозначно безопасную и нейтральную.
5. Тон — живой, дружелюбный, короткий.
6. Старайся не повторять одни и те же факты, которые вероятно уже публиковались — ищи разнообразные, не самые избитые темы.

Верни ТОЛЬКО JSON-объект, ничего больше."""


def call_claude():
    url = "https://api.anthropic.com/v1/messages"
    body = json.dumps({
        "model": "claude-sonnet-5",
        "max_tokens": 500,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": "Придумай и напиши следующий пост."}],
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["content"][0]["text"]


def parse_json_block(text):
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model output: " + text[:300])
    return json.loads(match.group(0))


def send_text(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHANNEL, "text": text}).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(url, data=data)) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_photo(text, photo_url):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = urllib.parse.urlencode(
        {"chat_id": TELEGRAM_CHANNEL, "caption": text, "photo": photo_url}
    ).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(url, data=data)) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    raw = call_claude()
    parsed = parse_json_block(raw)
    post_text = parsed["text"]
    category = parsed.get("category")
    use_photo = bool(parsed.get("use_photo", False))

    result = None
    if use_photo and category in PHOTO_POOL:
        photo_url = random.choice(PHOTO_POOL[category])
        try:
            result = send_photo(post_text, photo_url)
            if not result.get("ok"):
                raise RuntimeError(result)
        except Exception as e:
            print(f"Photo send failed ({e}), falling back to text", file=sys.stderr)
            result = None

    if result is None:
        result = send_text(post_text)

    if not result.get("ok"):
        print("Telegram API error:", result, file=sys.stderr)
        sys.exit(1)

    print(f"Posted (AI-generated) category={category} photo={use_photo} ok={result['ok']}")


if __name__ == "__main__":
    main()
