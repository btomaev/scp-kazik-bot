# Runtime `.TGS` slot generator

`slot_tgs.py` generates one Telegram animated sticker in memory and returns a fresh `BytesIO`. It does not write generated combinations to disk.

Requires Python 3.10+ and only uses the standard library.

## Symbols

| Value | Name | Emoji |
|---:|---|---|
| 0 | `cherry` | 🍒 |
| 1 | `lemon` | 🍋 |
| 2 | `orange` | 🍊 |
| 3 | `grapes` | 🍇 |
| 4 | `bell` | 🔔 |
| 5 | `seven` | 7️⃣ |

## Basic usage

```python
from slot_tgs import build_slot_tgs

sticker: BytesIO = build_slot_tgs("cherry", "bell", "seven")
assert sticker.tell() == 0
print(sticker.name)  # slot_0_4_5.tgs
```

By default every result is assembled on demand and discarded when the `BytesIO` is released. For frequently repeated outcomes, pass `use_cache=True`; the module retains at most 32 compressed stickers in RAM.

## aiogram 3

```python
from aiogram import Bot
from aiogram.types import BufferedInputFile
from slot_tgs import build_slot_tgs

async def send_slot(bot: Bot, chat_id: int, left, center, right):
    stream = build_slot_tgs(left, center, right)
    upload = BufferedInputFile(stream.getvalue(), filename=stream.name)
    return await bot.send_sticker(
        chat_id=chat_id,
        sticker=upload,
        emoji="🎰",
    )
```

## Direct multipart libraries

Libraries that accept file-like objects can receive the `BytesIO` directly:

```python
stream = build_slot_tgs(0, 4, 5)
files = {"sticker": (stream.name, stream, "application/x-tgsticker")}
```

## API

- `build_slot_tgs(left, center, right, use_cache=False) -> BytesIO`
- `slot_filename(left, center, right) -> str`
- `normalize_symbol(value) -> int`
- `clear_slot_cache()`
- `cache_info()`
- `SlotSymbol` enum
