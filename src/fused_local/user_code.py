from pathlib import Path
import importlib.util
import sys
from types import ModuleType

from watchfiles import awatch
import fused_local.lib


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


async def watch_reload_user_code(code_path: Path):
    # TODO what about when you have multiple files with imports?
    # when your file imports another?
    # basically we're not handling multiple files at all yet
    import_user_code(code_path)

    async for _ in awatch(code_path):
        # TODO: thread safety around `TileFunc._instances`
        # because tile render functions are run in a threadpool, there are race conditions here
        fused_local.lib.TileFunc._instances.clear()
        print(f"reloading {code_path}")
        import_user_code(code_path)


if __name__ == "__main__":
    module = import_user_code(Path("example.py"))
