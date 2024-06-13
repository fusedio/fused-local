from pathlib import Path
import importlib.util
import sys
from types import ModuleType

import anyio
from watchfiles import awatch


# HACK just hardcode for now
USER_CODE_PATH = Path.cwd() / "example.py"


def import_user_code(path: Path) -> ModuleType:
    # TODO see what streamlit does. they might just modify
    # sys.path, which might make more sense in the end.

    # https://stackoverflow.com/a/67692
    # https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly

    # TODO imports in the file don't seem to work
    # at least imports of other files in a non-module

    assert path.suffix == ".py", f"Expecting a python file, not {path}"

    module_name = path.stem
    assert (
        module_name.isidentifier()
    ), f"{module_name} is not a valid Python module name"

    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    assert spec.loader
    spec.loader.exec_module(module)
    return module


class RepeatEvent:
    _event: anyio.Event

    def __init__(self) -> None:
        self._event = anyio.Event()

    async def wait(self) -> None:
        await self._event.wait()

    def set(self) -> None:
        self._event.set()

    def clear(self) -> None:
        assert self._event.is_set(), "Clearing an un-set event could cause deadlocks"
        self._event = anyio.Event()

    def reset(self) -> None:
        self.set()
        self.clear()


async def watch_with_event(path: Path, event: RepeatEvent) -> RepeatEvent:
    async for _ in awatch(path):
        event.reset()

    return event


if __name__ == "__main__":
    module = import_user_code(Path("example.py"))
