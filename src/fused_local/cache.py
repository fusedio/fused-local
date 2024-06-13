import functools
from pathlib import Path
from typing import Callable, ParamSpec, TypeVar
import diskcache
from fused_local.hash import tokenize


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


# TODO can't actually pass `expire` into decorator, needs another level of nesting
def cache(func: Callable[P, R], expire: int | None = 24 * 60 * 60) -> Callable[P, R]:
    func_key = tokenize(func)

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        key = tokenize(func_key, *args, **kwargs)

        lock_key = f"{key}-lock"
        try:
            r = _cache[key]  # type: ignore
            # print(f"cache hit {func} {args}")
            return r  # type: ignore
        except KeyError:
            pass

        with diskcache.Lock(_cache, lock_key, expire=expire):
            # may have been added while waiting for lock
            try:
                r = _cache[key]  # type: ignore
                # print(f"cache hit 2 {func} {args}")
                return r  # type: ignore
            except KeyError:
                pass

            # print(f"actually computing {func} {args}")
            result = func(*args, **kwargs)
            _cache.set(key, result, expire=expire)
            return result

    return wrapper
