import json
import logging
import os
import pickle
import sys
import time
from datetime import datetime
from functools import wraps
from logging import Logger
from typing import Any, Callable

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


def get_db_key(*args, **kwargs) -> bytes:
    return pickle.dumps(
        (args, sorted(kwargs.items()))
    )


def serialize_value(value: Any) -> bytes:
    return pickle.dumps(value)


def deserialize_value(bytes) -> Any:
    return pickle.loads(bytes)


def get_leveldb_cache_fullpath(func_name: str) -> str:
    return os.path.join(CACHES_DIR, f"{func_name}_py_function_leveldb")


def leveldb_cache(func):
    """
    this is a decorator that caches result for the function 'func'.
    The cache is stored on disk, using LevelDB.
    
    The cache size is (currently) not configurable, and is unlimited
    """
    
    try:
        cache_fullpath = get_leveldb_cache_fullpath(func_name=func.__name__)
        db = plyvel.DB(cache_fullpath, create_if_missing=True)
    except plyvel.IOError:
        print(
            f"WARNING: leveldb_cache: IOERROR occurred when trying to open leveldb "
            f"for function `{func.__name__}`. function will NOT be cached",
            file=sys.stderr,
        )
        return func
    
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


TSV_SEPARATOR = "\t"


def populate_leveldb_cache(
    tsv_file: str,
    func_name: str,
    str_key_to_py_object: Callable[[str], Any] = None,
    str_value_to_py_object: Callable[[str], Any] = None,
) -> None:
    """
    This is a helper method for populating caches to be used by the leveldb_cache decorator.
    
    It is useful in cases we want to cache a function but we want to populate it
    manually because the first population is too expensive to be done by the cached function.
    
    This helper takes a tsv file with exactly two columns. the first value represents
    a function argument and the second value represents a function result.
    
    The cached function is assumed to take exactly one argument and that it is called
    like FUNC_NAME(arg1). i.e. the single argument is given without keyword
    
    Naturally, the argument and result are read from the tsv file as strings.
    if str_key_to_py_object/str_value_to_py_object are provided, they should
    be callables that take a string representation of the key/value respectively
    and return a python object.
    
    
    For example, if we'd like to populate a cache for the following function:
    
    def get_tx_size(txid:str) -> int:
        ...
    
    we should make the following call:
        populate_leveldb_cache("path/to/tsv", "get_tx_size", str_value_to_py_object=int)
    
    """
    db = plyvel.DB(get_leveldb_cache_fullpath(func_name=func_name), create_if_missing=True)
    with open(tsv_file) as f:
        for i, line in enumerate(f):
            line = line.strip()  # remove newline if exist
            k, v = line.split(TSV_SEPARATOR)
            if str_key_to_py_object:
                k = str_key_to_py_object(k)
            if str_value_to_py_object:
                v = str_value_to_py_object(v)
            
            # k is the argument and v is the result
            db.put(get_db_key(k), serialize_value(v))
