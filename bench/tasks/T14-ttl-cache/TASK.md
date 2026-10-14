Implement `TTLCache(maxsize, ttl, clock=time.monotonic)` in `src/ttlcache/cache.py`:

- `set(key, value)`: store the value with expiry `clock() + ttl`; setting an existing key replaces it and makes it most recently used.
- `get(key, default=None)`: return the value if present and not expired (`clock() < expiry`), and mark it most recently used; otherwise return `default`. Expired entries are removed when found.
- `delete(key)`: remove the key; raise `KeyError` if it is absent or expired.
- `key in cache` and `len(cache)` consider only non-expired entries.
- When inserting a new key into a full cache (counting only non-expired entries), first drop expired entries, then evict the least recently used entry.
- `maxsize` and `ttl` must be positive, else `ValueError`.

Add tests for the new behaviour in a new test file. Run the test suite with `python -m pytest -q`.
