import json
import logging
import os
import pickle
import sys
import time
from datetime import datetime
from functools import wraps
from logging import Logger
from typing import Any

import plyvel

from datatypes import Json


def print_json(o: Json):
    print(json.dumps(o, indent=4))


def now() -> str:
    """
    return current time in YYYY-MM-DD_HH:MM
    """
    return datetime.now().strftime("%Y-%m-%d_%H:%M")


def timeit(logger: Logger, print_args: bool = False):
    """
    the `timeit` decorator logs entering and exiting from a function, and the total
    time it ran.
    if `print_args` is True, the function arguments are also logged
    """
    
    def decorator(func):
        # the `wraps` decorator gives `wrapper` the attributes of func.
        # in particular, its name
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(
                f"Entering {func.__name__}"
                +
                (f" with args={args}, kwargs={kwargs}" if print_args else "")
            )
            t0 = time.time()
            result = func(*args, **kwargs)
            t1 = time.time()
            logger.info(
                f"Exiting {func.__name__}. Total runtime: {round(t1 - t0, 3)} seconds"
            )
            return result
        
        return wrapper
    
    return decorator


def setup_logging(
    logger_name: str = None,
    console: bool = True,
    filename: str = None,
    fmt: str = None
) -> Logger:
    """
    setup a logger with a specific format, console handler and possibly file handler
    
    :param logger_name: the logger to setup. If none, setup the root logger
    :param console: booleans indicating whether to log to standard output with level INFO
    :param filename: log file. If not None, log to this file with level DEBUG
    :param fmt: format for log messages. if None, a default format is used
    :return: the logger that was set-up
    """
    if fmt is None:
        fmt = "%(asctime)s: %(levelname)s: %(module)s: %(funcName)s: %(message)s"
    formatter = logging.Formatter(fmt=fmt, datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # the logger doesn't filter anything
    
    # console handler
    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        ch.setLevel(logging.INFO)
        logger.addHandler(ch)
    
    # file handler
    if filename:
        fh = logging.FileHandler(filename)
        fh.setFormatter(formatter)
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)
    
    return logger


CACHES_DIR = os.path.join(os.path.expandvars("$LN"), "data", "caches")


def leveldb_cache(func):
    """
    this is a decorator that caches result for the function 'func'.
    The cache is stored on disk, using LevelDB.
    
    The cache size is (currently) not configurable, and is unlimited
    """
    try:
        cache_name = f"{func.__name__}_py_function_leveldb"
        cache_fullpath = os.path.join(CACHES_DIR, cache_name)
        db = plyvel.DB(cache_fullpath, create_if_missing=True)
    except plyvel.IOError:
        print(
            f"WARNING: leveldb_cache: IOERROR occurred when trying to open leveldb `{cache_name}`. "
            f"function `{func.__name__}` will NOT be cached",
            file=sys.stderr,
        )
        return func
    
    def get_db_key(*args, **kwargs) -> bytes:
        return pickle.dumps(
            (args, sorted(kwargs.items()))
        )
    
    def serialize_value(value: Any) -> bytes:
        return pickle.dumps(value)
    
    def deserialize_value(bytes) -> Any:
        return pickle.loads(bytes)
    
    @wraps(func)
    def cached_func(*args, **kwargs):
        db_key = get_db_key(*args, **kwargs)
        value: bytes = db.get(db_key)
        if value:
            return deserialize_value(value)
        
        value = func(*args, **kwargs)
        
        db.put(db_key, serialize_value(value))
        return value
    
    return cached_func
