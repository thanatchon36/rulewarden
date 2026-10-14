import time


def retry(times, exceptions=(Exception,), delay=0.0, backoff=2.0, sleep=time.sleep):
    raise NotImplementedError
