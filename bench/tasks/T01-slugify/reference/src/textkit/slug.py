import re
import unicodedata

_SPECIAL = str.maketrans({"ß": "ss", "æ": "ae", "Æ": "AE", "ø": "o", "Ø": "O", "ł": "l", "Ł": "L"})


def _ascii(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.translate(_SPECIAL))
    return decomposed.encode("ascii", "ignore").decode("ascii")


def slugify(text: str, max_length: int | None = None, separator: str = "-") -> str:
    """Return an ASCII slug of `text`, optionally cut at a separator boundary."""
    if not separator:
        raise ValueError("separator must be non-empty")
    if max_length is not None and max_length < 1:
        raise ValueError("max_length must be at least 1")
    words = re.split(r"[^a-z0-9]+", _ascii(text).lower())
    slug = separator.join(w for w in words if w)
    if max_length is None or len(slug) <= max_length:
        return slug
    head = slug[:max_length]
    if slug[max_length:].startswith(separator):
        return head
    cut = head.rfind(separator)
    return head[:cut] if cut > 0 else head
