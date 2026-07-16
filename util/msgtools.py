from collections.abc import Callable
from typing import TypeVar


T = TypeVar('T')


def remove_command_prefix(text: str | None) -> str:
    if not text:
        return ''
    parts = text.split(maxsplit=1)
    return (parts or [''])[-1]


def _parse_value(
    text: str,
    converter: Callable[[str], T],
    index: int = 0,
    separator: str = ' ',
) -> tuple[T, int]:
    if not separator:
        raise ValueError('separator must not be empty')
    if index < 0 or index > len(text):
        raise ValueError('index is outside the text')

    while text.startswith(separator, index):
        index += len(separator)

    end = text.find(separator, index)
    if end == -1:
        end = len(text)

    return converter(text[index:end]), end


def parse_int(
    text: str,
    index: int = 0,
    separator: str = ' ',
) -> tuple[int, int]:
    '''Parse an integer token and return it with the next parsing index.'''
    return _parse_value(text, int, index, separator)


def parse_float(
    text: str,
    index: int = 0,
    separator: str = ' ',
) -> tuple[float, int]:
    '''Parse a floating-point token and return it with the next parsing index.'''
    return _parse_value(text, float, index, separator)


def parse_string(
    text: str,
    index: int = 0,
    separator: str = ' ',
) -> tuple[str, int]:
    '''Parse a string token and return it with the next parsing index.'''
    return _parse_value(text, str, index, separator)
