class HTTPStatusError(Exception):
    pass


def fetch_json(url: str, timeout: float = 5.0, retries: int = 0) -> object:
    raise NotImplementedError
