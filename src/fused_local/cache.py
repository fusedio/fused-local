import functools
from pathlib import Path
from typing import Callable, ParamSpec, TypeVar
import diskcache
from dask.base import tokenize, TokenizationError  # TODO remove dask dependency


P = ParamSpec("P")
R = TypeVar("R")

_cache = diskcache.FanoutCache(
    "cache",  # TODO global / temp directory
    shards=4,
    eviction_policy="least-recently-used",
    size_limit=2**30,  # 1 GB (default)
)
try:
    with open(Path(_cache.directory) / ".gitignore", "x") as f:
        # ensure a .gitignore exists for the cache directory
        f.write("*\n")
except FileExistsError:
    pass


def cache(func: Callable[P, R], expire: int | None = 5 * 60) -> Callable[P, R]:
    func_key = tokenize(func)

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            key = tokenize(func_key, *args, **kwargs, ensure_deterministic=True)
        except TokenizationError:
            # not cacheable
            # TODO log
            return func(*args, **kwargs)

        lock_key = f"{key}-lock"
        try:
            return _cache[key]  # type: ignore
        except KeyError:
            pass

        with diskcache.Lock(_cache, lock_key, expire=expire):
            # may have been added while waiting for lock
            try:
                return _cache[key]  # type: ignore
            except KeyError:
                pass

            result = func(*args, **kwargs)
            _cache.set(key, result, expire=expire)
            return result

    return wrapper
