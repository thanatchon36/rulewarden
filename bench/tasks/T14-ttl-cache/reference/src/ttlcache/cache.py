import time
from collections import OrderedDict

_MISSING = object()


class TTLCache:
    """LRU cache whose entries expire `ttl` seconds after they are set."""

    def __init__(self, maxsize, ttl, clock=time.monotonic):
        if maxsize <= 0 or ttl <= 0:
            raise ValueError("maxsize and ttl must be positive")
        self._max = maxsize
        self._ttl = ttl
        self._clock = clock
        self._data = OrderedDict()

    def _live(self, key):
        item = self._data.get(key, _MISSING)
        if item is _MISSING:
            return _MISSING
        value, expiry = item
        if self._clock() >= expiry:
            del self._data[key]
            return _MISSING
        return value

    def _purge(self):
        now = self._clock()
        for key in [k for k, (_, exp) in self._data.items() if now >= exp]:
            del self._data[key]

    def set(self, key, value):
        if key in self._data:
            del self._data[key]
        else:
            self._purge()
            while len(self._data) >= self._max:
                self._data.popitem(last=False)
        self._data[key] = (value, self._clock() + self._ttl)

    def get(self, key, default=None):
        value = self._live(key)
        if value is _MISSING:
            return default
        self._data.move_to_end(key)
        return value

    def delete(self, key):
        if self._live(key) is _MISSING:
            raise KeyError(key)
        del self._data[key]

    def __contains__(self, key):
        return self._live(key) is not _MISSING

    def __len__(self):
        self._purge()
        return len(self._data)
