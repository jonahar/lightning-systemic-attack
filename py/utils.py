import json
import time
from datetime import datetime
from functools import wraps

from datatypes import Json


def print_json(o: Json):
    print(json.dumps(o, indent=4))


def now() -> str:
    """
    return current time in YYYY-MM-DD_HH:MM
    """
    return datetime.now().strftime("%Y-%m-%d_%H:%M")


def timeit(func):
    # the `wraps` decorator gives `wrapper` the attributes of func.
    # in particular, its name
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"Entering {func.__name__}")
        t0 = time.time()
        result = func(*args, **kwargs)
        t1 = time.time()
        print(
            f"Exiting {func.__name__}. function ran for {t1 - t0} seconds"
        )
        return result
    
    return wrapper
