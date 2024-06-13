from pathlib import Path
import pydantic


class Config(pydantic.BaseModel):
    user_code_path: Path
    url: str
    dev: bool = False
    open_browser: bool = False


# NOTE: set in `serve.py`.
# There must be a better way to do this in FastAPI... unclear
# how to pass arguments in (to the lifetime function) at runtime
_config: Config | None = None


def config() -> Config:
    assert _config, "No config set, app is not served!"
    return _config
