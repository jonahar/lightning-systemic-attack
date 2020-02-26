import json
import logging
import os
import pickle
import sqlite3
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


def get_db_str_key(*args, **kwargs) -> str:
    """
    this methods return a string representation of its arguments.
    
    Important: different arguments should have different string representation
    """
    args_str = [str(arg) for arg in args]
    kwargs_str = [f"{k}={kwargs[k]}" for k in sorted(kwargs.keys())]
    return ",".join(args_str + kwargs_str)


def serialize_value(value: Any) -> bytes:
    return pickle.dumps(value)


def deserialize_value(serialized_value: bytes) -> Any:
    return pickle.loads(serialized_value)


def get_leveldb_cache_fullpath(func_name: str) -> str:
    return os.path.join(CACHES_DIR, f"{func_name}_py_function_leveldb")


def leveldb_cache(
    value_to_str: Callable[[Any], str],
    str_to_value: Callable[[str], Any],
    key_to_str: Callable[..., str] = None,
    db_path: str = None,

):
    """
    this is a decorator that caches result for the function 'func'.
    The cache is stored on disk, using LevelDB.
    
    The cache size is (currently) not configurable, and is unlimited
    """
    
    if key_to_str is None:
        key_to_str = get_db_str_key
    
    def decorator(func):
        try:
            cache_fullpath = db_path if db_path else get_leveldb_cache_fullpath(func_name=func.__name__)
            db = plyvel.DB(cache_fullpath, create_if_missing=True)
        except plyvel.IOError as e:
            print(
                f"WARNING: leveldb_cache: IOERROR occurred when trying to open leveldb "
                f"for function `{func.__name__}`. function will NOT be cached. "
                f"Error: {type(e)}: {str(e)}",
                file=sys.stderr,
            )
            return func
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            db_key = key_to_str(*args, **kwargs).encode("utf-8")
            value: bytes = db.get(db_key)
            if value:
                return str_to_value(value.decode("utf-8"))
            
            value = func(*args, **kwargs)
            
            db.put(db_key, value_to_str(value).encode("utf-8"))
            return value
        
        return wrapper
    
    return decorator


def get_sqlite_cache_fullpath(func_name: str) -> str:
    return os.path.join(CACHES_DIR, f"{func_name}_py_function_cache.sqlite")


def sqlite_cache(
    value_to_str: Callable[[Any], str],
    str_to_value: Callable[[str], Any],
    key_to_str: Callable[..., str] = None,
    db_path: str = None,
):
    """
    This decorator caches results of function calls in a sqlite DB on disk.
    The cache size is (currently) not configurable, and is unlimited.
    
    Each DB entry is a pair of input/output, representing function arguments and
    the function result for these arguments. Both represented as strings.
    
    The decision to store only strings in the DB was made to allow other
    applications (specifically, not python) to open the DB and to be able to easily
    parse and understand it.
    
    Args:
        value_to_str: a callable that takes results of the cached function and return
                      their string representation
        
        str_to_value: a callable that takes string representation of some result of
                      the cached function and return the value it represents
        
        key_to_str: a callable that takes any combination of arguments and returns
                    a string representing this set of arguments. if None (default),
                    a default conversion method will be used. In that case you should
                    make sure that different arguments have different string representation,
                    or they will be considered equal
                    
        db_path: full path to the db file. if None (default) use a default one
    
    
    
    Usage examples:
        
    @sqlite_cache(value_to_str=str, str_to_value=float)
    def foo(arg1: str, arg2: float) -> float:
        ...

    import json
    @sqlite_cache(value_to_str=json.dumps, str_to_value=json.loads)
    def bar(arg1: str, arg2: str) -> List[str]:
        ...
    
    """
    
    if key_to_str is None:
        key_to_str = get_db_str_key
    
    def decorator(func):
        try:
            cache_fullpath = (
                db_path if db_path else get_sqlite_cache_fullpath(func_name=func.__name__)
            )
            conn = sqlite3.connect(cache_fullpath)
            c = conn.cursor()
            c.execute(
                f"CREATE TABLE IF NOT EXISTS {func.__name__} "
                f"(input TEXT PRIMARY KEY, output TEXT);"
            )
        except sqlite3.Error as e:
            print(
                f"WARNING: sqlite_cache: ERROR occurred when trying to open sqlite db "
                f"for function `{func.__name__}`. function will NOT be cached. Error: {e}",
                file=sys.stderr,
            )
            return func
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            db_key = key_to_str(*args, **kwargs)
            res = c.execute(
                f"select output from {func.__name__} where input=(?)",
                (db_key,)
            )
            line = res.fetchone()
            if line:
                # key exists
                serialized_value = line[0]
                return str_to_value(serialized_value)
            
            value = func(*args, **kwargs)
            
            c.execute(
                F"INSERT INTO {func.__name__} (input, output) values (?, ?)",
                (db_key, value_to_str(value)),
            )
            conn.commit()
            
            return value
        
        return wrapper
    
    return decorator
