import time


class TTLCache:
    def __init__(self, maxsize, ttl, clock=time.monotonic):
        raise NotImplementedError
