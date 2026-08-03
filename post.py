#!/usr/bin/env python3
"""Post the next item from posts_bank.json to a Telegram channel, cycling
through the bank without repeats until exhausted, then reshuffling.

Requires env vars:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHANNEL   (defaults to @allbegoods)
"""
import json
import os
import random
import sys
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BANK_PATH = os.path.join(BASE_DIR, "posts_bank.json")
STATE_PATH = os.path.join(BASE_DIR, "posted_state.json")

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@allbegoods")


def load_bank():
    with open(BANK_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_remaining(all_ids):
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)
        remaining = state.get("remaining_ids") or []
        # drop any ids no longer present in the bank (e.g. bank was edited)
        remaining = [i for i in remaining if i in all_ids]
    else:
        remaining = []
    if not remaining:
        remaining = all_ids[:]
        random.shuffle(remaining)
    return remaining


def save_remaining(remaining):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"remaining_ids": remaining}, f, ensure_ascii=False)


def send_text(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHANNEL, "text": text}).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(url, data=data)) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_photo(text, photo_url):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    data = urllib.parse.urlencode(
        {"chat_id": CHANNEL, "caption": text, "photo": photo_url}
    ).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(url, data=data)) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    bank = load_bank()
    by_id = {p["id"]: p for p in bank}
    all_ids = [p["id"] for p in bank]

    remaining = load_remaining(all_ids)
    next_id = remaining.pop(0)
    post = by_id[next_id]

    result = None
    if post.get("photo"):
        try:
            result = send_photo(post["text"], post["photo"])
            if not result.get("ok"):
                raise RuntimeError(result)
        except Exception as e:
            print(f"Photo send failed ({e}), falling back to text", file=sys.stderr)
            result = None

    if result is None:
        result = send_text(post["text"])

    if not result.get("ok"):
        print("Telegram API error:", result, file=sys.stderr)
        sys.exit(1)

    save_remaining(remaining)
    print(f"Posted id={next_id} category={post['category']} ok={result['ok']}")


if __name__ == "__main__":
    main()
