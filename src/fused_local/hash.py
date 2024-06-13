"""
(hopefully) deterministic hashing of Python objects.

Getting a hash of an arbitrary Python object (especially a function) that's stable
across interpreter restarts, but also accounts for closed-over variables, etc., is
rather hard.

Some implementations (like `dask.base.tokenize`) land on pickle/cloudpickle at the core,
and just hash that byte stream. However, pickle, cloudpickle, and dill are not
determinstic.

* Cloudpickle: https://github.com/cloudpipe/cloudpickle/issues/453
* Dill: https://github.com/uqfoundation/dill/issues/19

Because we'll be caching user code based on the contents of the function, and importing
their code in many separate processes and, eventually, separate machines, it's essential
that our hashing is stable.

This tries to get somewhat better stable hashing via a mashup of dask's `tokenize`
functions and some tricks for dealing with the code objects of functions cribbed from
cloudpickle.
"""

import dataclasses
import datetime
import decimal
import dis
import hashlib
import importlib.metadata
import inspect
import opcode
import pathlib
import pickle
import types
from collections.abc import Mapping, Sequence, Set
from functools import partial, singledispatch
from typing import Iterator
import weakref

import cloudpickle


def tokenize(*args: object, **kwargs: object) -> str:
    "Deterministically hash an object."
    hasher = hashlib.sha256()
    for obj in args:
        _tokenize_update(obj, hasher)
    for k, obj in kwargs.items():
        hasher.update(k.encode())
        _tokenize_update(obj, hasher)
    return hasher.hexdigest()


def _tokenize_update(obj: object, hasher) -> None:
    for x in normalize(obj):
        hasher.update(x if isinstance(x, bytes) else str(x).encode())


@singledispatch
def normalize(obj: object) -> Iterator[object]:
    "Convert an object into an iterator of things that are ready to hash: bytes, or objects that can have `str` called on them."
    dask_tokenize = getattr(obj, "__dask_tokenize__", None)
    if callable(dask_tokenize):
        yield dask_tokenize()

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        yield from _normalize_dataclass(obj)

    yield from _normalize_with_pickle(obj)

    # raise NotImplementedError(f"normalize not implemented for {type(obj)}")


@normalize.register
def normalize_identity(
    obj: int
    | float
    | str
    | bytes
    | None
    | types.EllipsisType
    | slice
    | complex
    | decimal.Decimal
    | datetime.date
    | datetime.time
    | datetime.datetime
    | datetime.timedelta
    | pathlib.PurePath,
) -> Iterator[object]:
    yield obj


@normalize.register
def normalize_sequence(obj: Sequence) -> Iterator[object]:
    yield type(obj)
    for x in obj:
        yield from normalize(x)


@normalize.register
def normalize_mapping(obj: Mapping) -> Iterator[object]:
    yield type(obj)
    for k, v in obj.items():
        yield from normalize(k)
        yield from normalize(v)


@normalize.register
def normalize_set(obj: Set) -> Iterator[object]:
    yield type(obj)
    for x in sorted(obj):
        yield from normalize(x)


@normalize.register
def normalize_partial(obj: partial) -> Iterator[object]:
    yield from normalize(obj.func)
    yield from normalize(obj.args)
    yield from normalize(obj.keywords)


@normalize.register
def normalize_function(obj: types.FunctionType) -> Iterator[object]:
    yield from normalize(obj.__code__)  # --> CodeType
    yield from normalize(obj.__defaults__)
    yield from normalize(obj.__kwdefaults__)
    yield from normalize(obj.__closure__)  # --> CellType

    # Normalize globals, but only the ones the function actually references.
    # This ends up using `dis` on the bytecode, looking for `LOAD_GLOBAL` instructions,
    # and seeing what names they refer to.
    # https://github.com/cloudpipe/cloudpickle/blob/f111f7ab6d302e9/cloudpickle/cloudpickle.py#L719
    global_names_used = _extract_code_globals(obj.__code__)
    for k in global_names_used:
        if v := obj.__globals__.get(k):
            yield from normalize(v)


@normalize.register
def normalize_code(code: types.CodeType) -> Iterator[object]:
    # FIXME this is probably not sufficient?
    # What if the function references another function, and that one changes?
    # What if an imported function changes?
    yield code.co_code
    yield from normalize(code.co_consts)
    yield from normalize(code.co_names)


@normalize.register
def normalize_cell(cell: types.CellType) -> Iterator[object]:
    # https://github.com/cloudpipe/cloudpickle/blob/f111f7ab6d3/cloudpickle/cloudpickle.py#L472-L477
    try:
        contents = cell.cell_contents
    except ValueError:
        yield None

    yield from normalize(contents)


@normalize.register
def normalize_bound_method(
    meth: types.MethodType | types.MethodWrapperType,
) -> Iterator[object]:
    # https://github.com/dask/dask/blob/da1d53af6fcbf53/dask/base.py#L1185-L1187
    yield meth.__name__
    yield from normalize(meth.__self__)


@normalize.register
def normalize_module(obj: types.ModuleType) -> Iterator[object]:
    # HACK how should we actually normalize a module??
    yield type(obj)
    yield obj.__name__
    try:
        yield importlib.metadata.version(obj.__name__)
    except importlib.metadata.PackageNotFoundError:
        # TODO maybe via pickle?? not sure that adds anything though.
        pass


@normalize.register
def normalize_builtin(func: types.BuiltinFunctionType) -> Iterator[object]:
    # https://github.com/dask/dask/blob/da1d53af6fcbf53/dask/base.py#L1190-L1197
    self = getattr(func, "__self__", None)
    if self is not None and not inspect.ismodule(self):
        yield from normalize_bound_method(func)
    else:
        # HACK no idea if this makes sense. dask pickles it, but we know that's nondeterministic.
        yield str(func)


def _normalize_dataclass(obj) -> Iterator[object]:
    # https://github.com/dask/dask/blob/da1d53af6fcbf53/dask/base.py#L1254-L1262
    yield type(obj)

    for field in dataclasses.fields(obj):
        yield field.name
        yield from normalize(getattr(obj, field.name, None))

    params = obj.__dataclass_params__
    for attr in params.__slots__:
        yield attr
        yield from normalize(getattr(params, attr))


def _normalize_with_pickle(o: object) -> Iterator[object]:
    # https://github.com/dask/dask/blob/da1d53af6fcbf/dask/base.py#L1237-L1252
    buffers: list[pickle.PickleBuffer] = []
    pik: bytes | None
    try:
        pik = pickle.dumps(o, protocol=5, buffer_callback=buffers.append)
        if b"__main__" in pik:
            pik = None
    except Exception:
        pik = None

    if pik is None:
        buffers.clear()
        pik = cloudpickle.dumps(o, protocol=5, buffer_callback=buffers.append)

    yield pik
    yield from buffers


_extract_code_globals_cache = weakref.WeakKeyDictionary()


# https://github.com/cloudpipe/cloudpickle/blob/f111f7ab6d302e9b1/cloudpickle/cloudpickle.py#L305
def _extract_code_globals(co: types.CodeType) -> dict[str, None]:
    """Find all globals names read or written to by codeblock co."""
    out_names = _extract_code_globals_cache.get(co)
    if out_names is None:
        # We use a dict with None values instead of a set to get a
        # deterministic order and avoid introducing non-deterministic pickle
        # bytes as a results.
        out_names = {name: None for name in _walk_global_ops(co)}

        # Declaring a function inside another one using the "def ..." syntax
        # generates a constant code object corresponding to the one of the
        # nested function's As the nested function may itself need global
        # variables, we need to introspect its code, extract its globals, (look
        # for code object in it's co_consts attribute..) and add the result to
        # code_globals
        if co.co_consts:
            for const in co.co_consts:
                if isinstance(const, types.CodeType):
                    out_names.update(_extract_code_globals(const))

        _extract_code_globals_cache[co] = out_names

    return out_names


# https://github.com/cloudpipe/cloudpickle/blob/f111f7ab6d302e/cloudpickle/cloudpickle.py#L380-L383
STORE_GLOBAL = opcode.opmap["STORE_GLOBAL"]
DELETE_GLOBAL = opcode.opmap["DELETE_GLOBAL"]
LOAD_GLOBAL = opcode.opmap["LOAD_GLOBAL"]
GLOBAL_OPS = (STORE_GLOBAL, DELETE_GLOBAL, LOAD_GLOBAL)


# https://github.com/cloudpipe/cloudpickle/blob/f111f7ab6d302e/cloudpickle/cloudpickle.py#L403-L408
def _walk_global_ops(code) -> Iterator[str]:
    """Yield referenced name for global-referencing instructions in code."""
    for instr in dis.get_instructions(code):
        op = instr.opcode
        if op in GLOBAL_OPS:
            yield instr.argval


# TODO numpy, pandas, etc
# might be better to steal from dask
