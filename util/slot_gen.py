'''Runtime generator for deterministic Telegram animated slot stickers (.TGS).

No files are created on disk. ``build_slot_tgs`` returns a fresh ``BytesIO``
positioned at byte 0 and ready to upload through a Telegram bot library.
'''

from __future__ import annotations

__all__ = [
    'SlotSymbol',
    'SYMBOLS',
    'build_slot_tgs',
    'cache_info',
    'clear_slot_cache',
    'normalize_symbol',
    'slot_filename',
]

import gzip
import json
from enum import IntEnum
from functools import lru_cache
from io import BytesIO
from typing import Final, TypeAlias

FR: Final = 60
OP: Final = 180
TGS_MAX_BYTES: Final = 64 * 1024

SYMBOLS: Final = (
    ('cherry', '🍒'),
    ('lemon', '🍋'),
    ('orange', '🍊'),
    ('grapes', '🍇'),
    ('bell', '🔔'),
    ('seven', '7️⃣'),
)


class SlotSymbol(IntEnum):
    CHERRY = 0
    LEMON = 1
    ORANGE = 2
    GRAPES = 3
    BELL = 4
    SEVEN = 5


SymbolInput: TypeAlias = int | str | SlotSymbol

_NAME_TO_INDEX: Final = {name: index for index, (name, _) in enumerate(SYMBOLS)}
_EMOJI_TO_INDEX: Final = {emoji: index for index, (_, emoji) in enumerate(SYMBOLS)}
# Common spelling variants accepted by the public API.
_ALIASES: Final = {
    'cherries': 0,
    'grape': 3,
    '7': 5,
    '7️⃣': 5,
}

def prop(v):
    return {'a': 0, 'k': v}


def transform(p=(0, 0), a=(0, 0), s=(100, 100), r=0, o=100):
    return {
        'ty': 'tr', 'p': prop(list(p)), 'a': prop(list(a)), 's': prop(list(s)),
        'r': prop(r), 'o': prop(o), 'sk': prop(0), 'sa': prop(0), 'nm': 'Transform'
    }


def fill(rgb, opacity=100):
    return {'ty': 'fl', 'c': prop([rgb[0], rgb[1], rgb[2], 1]), 'o': prop(opacity), 'r': 1, 'nm': 'Fill'}


def stroke(rgb, width=4, opacity=100):
    return {'ty': 'st', 'c': prop([rgb[0], rgb[1], rgb[2], 1]), 'o': prop(opacity), 'w': prop(width), 'lc': 2, 'lj': 2, 'ml': 4, 'nm': 'Stroke'}


def ellipse(size, pos=(0, 0)):
    return {'ty': 'el', 'd': 1, 's': prop(list(size)), 'p': prop(list(pos)), 'nm': 'Ellipse'}


def rect(size, pos=(0, 0), radius=0):
    return {'ty': 'rc', 'd': 1, 's': prop(list(size)), 'p': prop(list(pos)), 'r': prop(radius), 'nm': 'Rect'}


def path(vertices, closed=True):
    zeros = [[0, 0] for _ in vertices]
    return {'ty': 'sh', 'ks': prop({'i': zeros, 'o': zeros, 'v': vertices, 'c': closed}), 'nm': 'Path'}


def group(name, items, pos=(0, 0), scale=(100, 100), rotation=0, opacity=100):
    return {'ty': 'gr', 'it': items + [transform(pos, (0, 0), scale, rotation, opacity)], 'nm': name}


def shape_layer(name, shapes, ind, ip=0, op=OP, pos=(0, 0), anchor=(0, 0), scale=(100, 100), opacity=100):
    return {
        'ddd': 0, 'ind': ind, 'ty': 4, 'nm': name, 'sr': 1,
        'ks': {
            'o': prop(opacity), 'r': prop(0), 'p': prop([pos[0], pos[1], 0]),
            'a': prop([anchor[0], anchor[1], 0]), 's': prop([scale[0], scale[1], 100])
        },
        'ao': 0, 'shapes': shapes, 'ip': ip, 'op': op, 'st': 0, 'bm': 0
    }


def symbol_groups(symbol_index, y):
    # All coordinates are local to a 100px-wide reel.
    if symbol_index == 0:  # cherries
        return [
            group('stems', [path([[-8, -5], [2, -28], [18, -34]], False), stroke((0.12, 0.55, 0.22), 5)], pos=(50, y)),
            group('cherry-left', [ellipse((34, 34)), fill((0.91, 0.09, 0.16)), stroke((0.55, 0.02, 0.05), 3)], pos=(36, y + 10)),
            group('cherry-right', [ellipse((36, 36)), fill((1.0, 0.14, 0.20)), stroke((0.55, 0.02, 0.05), 3)], pos=(64, y + 12)),
            group('shine', [ellipse((8, 8)), fill((1.0, 0.65, 0.68))], pos=(58, y + 5)),
        ]
    if symbol_index == 1:  # lemon
        return [
            group('lemon', [ellipse((68, 48)), fill((1.0, 0.84, 0.05)), stroke((0.75, 0.54, 0.0), 4)], pos=(50, y), rotation=-12),
            group('leaf', [path([[0, -12], [18, 0], [0, 12], [-10, 0]]), fill((0.20, 0.68, 0.20))], pos=(75, y - 23), rotation=-18),
            group('shine', [ellipse((16, 7)), fill((1.0, 0.96, 0.55))], pos=(35, y - 9), rotation=-12),
        ]
    if symbol_index == 2:  # orange
        return [
            group('orange', [ellipse((60, 60)), fill((1.0, 0.49, 0.03)), stroke((0.78, 0.28, 0.0), 4)], pos=(50, y + 3)),
            group('leaf', [path([[0, -13], [20, 0], [0, 11], [-11, 0]]), fill((0.12, 0.62, 0.19))], pos=(67, y - 27), rotation=-24),
            group('shine', [ellipse((12, 8)), fill((1.0, 0.73, 0.32))], pos=(34, y - 7), rotation=-25),
        ]
    if symbol_index == 3:  # grapes
        circles = []
        coords = [(50,-20),(36,-8),(52,-5),(67,-7),(30,8),(47,10),(64,9),(40,26),(57,25)]
        for idx,(cx,cy) in enumerate(coords):
            circles.append(group(f'grape-{idx}', [ellipse((24,24)), fill((0.46,0.16,0.73)), stroke((0.27,0.07,0.48),2)], pos=(cx,y+cy)))
        circles += [
            group('stem', [path([[0, 8], [5, -13], [15, -23]], False), stroke((0.16, 0.52, 0.18), 5)], pos=(48, y - 24)),
            group('leaf', [path([[0,-11],[20,0],[0,12],[-11,0]]), fill((0.15,0.64,0.18))], pos=(67,y-31), rotation=-20)
        ]
        return circles
    if symbol_index == 4:  # bell
        return [
            group('bell-body', [path([[-30,18],[-23,-4],[-15,-24],[0,-34],[15,-24],[23,-4],[30,18]]), fill((1.0,0.72,0.05)), stroke((0.72,0.40,0.0),4)], pos=(50,y)),
            group('bell-rim', [rect((70,14),(0,0),7), fill((1.0,0.63,0.02)), stroke((0.72,0.40,0.0),3)], pos=(50,y+22)),
            group('clapper', [ellipse((16,16)), fill((0.83,0.42,0.0)), stroke((0.60,0.28,0.0),2)], pos=(50,y+35)),
            group('shine', [ellipse((10,20)), fill((1.0,0.90,0.40))], pos=(39,y-8), rotation=10),
        ]
    # seven
    return [
        group('seven-top', [rect((64,16),(0,0),4), fill((0.95,0.08,0.12)), stroke((0.60,0.0,0.04),3)], pos=(50,y-24)),
        group('seven-diagonal', [path([[-2,-28],[20,-28],[-8,34],[-27,34]]), fill((0.95,0.08,0.12)), stroke((0.60,0.0,0.04),3)], pos=(54,y+2)),
        group('shine', [path([[-20,-28],[7,-28],[3,-20],[-17,-20]]), fill((1.0,0.52,0.54))], pos=(50,y-2)),
    ]


def reel_sequence(initial, target, settle):
    changes = [(0, initial), (8, initial)]
    step = 5
    k = 0
    for t in range(8, settle, step):
        changes.append((t, (initial + k) % len(SYMBOLS)))
        k += 1
    changes.append((settle, target))
    changes.append((OP - 1, target))
    # Deduplicate timestamps, keeping the latest value.
    dedup = {}
    for t, sym in changes:
        dedup[t] = sym
    return sorted(dedup.items())


def opacity_for_symbol(sequence, symbol_index):
    return {
        'a': 1,
        'k': [
            {'t': t, 's': [100 if current == symbol_index else 0], 'h': 1}
            for t, current in sequence
        ]
    }


def scale_for_symbol(symbol_index, target, settle):
    if symbol_index != target:
        return prop([100, 100, 100])
    return {
        'a': 1,
        'k': [
            {'t': 0, 's': [100, 100, 100], 'h': 1},
            {'t': settle, 's': [100, 100, 100], 'e': [112, 112, 100],
             'o': {'x': [0.25], 'y': [0]}, 'i': {'x': [0.75], 'y': [1]}},
            {'t': settle + 7, 's': [112, 112, 100], 'e': [96, 96, 100],
             'o': {'x': [0.25], 'y': [0]}, 'i': {'x': [0.75], 'y': [1]}},
            {'t': settle + 14, 's': [96, 96, 100], 'e': [100, 100, 100],
             'o': {'x': [0.25], 'y': [0]}, 'i': {'x': [0.75], 'y': [1]}},
            {'t': settle + 22, 's': [100, 100, 100]},
        ]
    }


def reel_symbol_layer(ind, x, symbol_index, target, settle, initial):
    sequence = reel_sequence(initial, target, settle)
    layer = shape_layer(
        f'Reel symbol {symbol_index}',
        symbol_groups(symbol_index, 260),
        ind,
        pos=(0, 0),
    )
    layer['ks']['o'] = opacity_for_symbol(sequence, symbol_index)
    layer['ks']['s'] = scale_for_symbol(symbol_index, target, settle)
    layer['ks']['a'] = prop([50, 260, 0])
    layer['ks']['p'] = prop([x, 260, 0])
    return layer


def make_animation(result):
    # In Lottie layer arrays, earlier layers render above later layers.
    layers = []
    ind = 1
    # Foreground bezel pieces cover the moving strips outside the windows.
    bezel_groups = [
        group('top-cover', [rect((430, 128), radius=34), fill((0.16, 0.24, 0.36)), stroke((0.06, 0.09, 0.14), 8)], pos=(256, 148)),
        group('bottom-cover', [rect((430, 128), radius=34), fill((0.16, 0.24, 0.36)), stroke((0.06, 0.09, 0.14), 8)], pos=(256, 372)),
        group('left-cover', [rect((70, 152), radius=18), fill((0.16, 0.24, 0.36))], pos=(71, 260)),
        group('right-cover', [rect((70, 152), radius=18), fill((0.16, 0.24, 0.36))], pos=(441, 260)),
        group('divider-1', [rect((18, 152), radius=8), fill((0.16, 0.24, 0.36))], pos=(201, 260)),
        group('divider-2', [rect((18, 152), radius=8), fill((0.16, 0.24, 0.36))], pos=(311, 260)),
        group('window-outline', [rect((368, 154), radius=24), stroke((0.04, 0.07, 0.12), 8)], pos=(256, 260)),
        group('title-lamp-left', [ellipse((18,18)), fill((1.0,0.82,0.10)), stroke((0.65,0.35,0.0),2)], pos=(154, 121)),
        group('title-lamp-mid', [ellipse((18,18)), fill((1.0,0.82,0.10)), stroke((0.65,0.35,0.0),2)], pos=(256, 110)),
        group('title-lamp-right', [ellipse((18,18)), fill((1.0,0.82,0.10)), stroke((0.65,0.35,0.0),2)], pos=(358, 121)),
        group('button', [ellipse((58,58)), fill((0.92,0.13,0.18)), stroke((0.48,0.02,0.05),5)], pos=(256, 389)),
        group('button-shine', [ellipse((22,12)), fill((1.0,0.55,0.58))], pos=(245, 377), rotation=-22),
    ]
    layers.append(shape_layer('Front Bezel', bezel_groups, ind)); ind += 1

    # Six symbol layers per reel; opacity cycles imitate spinning without masks.
    for x, target, settle, initial in zip((145, 256, 367), result, (100, 112, 124), (0, 2, 4)):
        for symbol_index in range(len(SYMBOLS)):
            layers.append(reel_symbol_layer(ind, x, symbol_index, target, settle, initial))
            ind += 1

    # White window background below reels.
    window_bg = [
        group('window-bg', [rect((368,154), radius=24), fill((0.97,0.98,1.0)), stroke((0.04,0.07,0.12),8)], pos=(256,260)),
        group('inner-shadow-top', [rect((350,12), radius=6), fill((0.73,0.78,0.85),65)], pos=(256,194)),
        group('inner-shadow-bottom', [rect((350,12), radius=6), fill((0.73,0.78,0.85),65)], pos=(256,326)),
    ]
    layers.append(shape_layer('Window Background', window_bg, ind)); ind += 1

    # Back body and feet.
    back = [
        group('body', [rect((430,330), radius=42), fill((0.21,0.33,0.52)), stroke((0.04,0.07,0.12),10)], pos=(256,260)),
        group('top-highlight', [rect((385,14), radius=7), fill((0.36,0.53,0.76),70)], pos=(256,112)),
        group('foot-left', [rect((82,30), radius=12), fill((0.06,0.09,0.14))], pos=(155,438)),
        group('foot-right', [rect((82,30), radius=12), fill((0.06,0.09,0.14))], pos=(357,438)),
    ]
    layers.append(shape_layer('Machine Body', back, ind)); ind += 1

    return {
        'v': '5.7.4', 'fr': FR, 'ip': 0, 'op': OP, 'w': 512, 'h': 512,
        'nm': f'Slot {result[0]}-{result[1]}-{result[2]}', 'ddd': 0,
        'assets': [], 'layers': layers, 'markers': []
    }

def normalize_symbol(value: SymbolInput) -> int:
    '''Convert an index, enum, slug or supported emoji to an integer 0..5.'''
    if isinstance(value, bool):
        raise TypeError('bool is not a valid slot symbol')

    if isinstance(value, (int, SlotSymbol)):
        index = int(value)
        if 0 <= index < len(SYMBOLS):
            return index
        raise ValueError(f'symbol index must be in 0..{len(SYMBOLS) - 1}, got {index}')

    if not isinstance(value, str):
        raise TypeError(f'symbol must be int, str or SlotSymbol, got {type(value).__name__}')

    key = value.strip().lower()
    if key in _NAME_TO_INDEX:
        return _NAME_TO_INDEX[key]
    if value.strip() in _EMOJI_TO_INDEX:
        return _EMOJI_TO_INDEX[value.strip()]
    if key in _ALIASES:
        return _ALIASES[key]

    allowed = ', '.join(name for name, _ in SYMBOLS)
    raise ValueError(f'unknown symbol {value!r}; allowed names: {allowed}, or indices 0..5')


def slot_filename(left: SymbolInput, center: SymbolInput, right: SymbolInput) -> str:
    '''Return a stable upload filename for a combination.'''
    result = tuple(normalize_symbol(value) for value in (left, center, right))
    return f'slot_{result[0]}_{result[1]}_{result[2]}.tgs'


@lru_cache(maxsize=32)
def _build_tgs_bytes(result: tuple[int, int, int]) -> bytes:
    '''Build and optionally retain one compressed sticker in process memory.'''
    animation = make_animation(result)
    raw_json = json.dumps(
        animation,
        separators=(',', ':'),
        ensure_ascii=False,
    ).encode('utf-8')

    output = BytesIO()
    # Empty filename and mtime=0 make the gzip payload reproducible.
    with gzip.GzipFile(
        filename='',
        mode='wb',
        fileobj=output,
        compresslevel=9,
        mtime=0,
    ) as archive:
        archive.write(raw_json)

    payload = output.getvalue()
    if len(payload) > TGS_MAX_BYTES:
        raise RuntimeError(
            f'generated TGS is {len(payload)} bytes, exceeding {TGS_MAX_BYTES} bytes'
        )
    return payload


def build_slot_tgs(
    left: SymbolInput,
    center: SymbolInput,
    right: SymbolInput,
    *,
    use_cache: bool = False,
) -> BytesIO:
    '''Build one animated slot sticker entirely in memory.

    Args:
        left, center, right: Symbol indices 0..5, ``SlotSymbol`` values,
            slugs such as ``'cherry'``/``'seven'``, or supported emoji.
        use_cache: Retain up to 32 recently generated combinations in RAM. The returned
            ``BytesIO`` is always a new independent object.

    Returns:
        A fresh ``BytesIO`` positioned at 0.
    '''
    result = tuple(normalize_symbol(value) for value in (left, center, right))

    if use_cache:
        payload = _build_tgs_bytes(result)
    else:
        # Bypass lru_cache without duplicating the builder implementation.
        payload = _build_tgs_bytes.__wrapped__(result)

    stream = BytesIO(payload)
    # Some libraries inspect ``name`` on file-like objects.
    stream.name = slot_filename(*result)  # type: ignore[attr-defined]
    stream.seek(0)
    return stream


def clear_slot_cache() -> None:
    '''Release all generated combinations retained by the in-memory cache.'''
    _build_tgs_bytes.cache_clear()


def cache_info():
    '''Expose cache statistics, useful for monitoring long-running bots.'''
    return _build_tgs_bytes.cache_info()
