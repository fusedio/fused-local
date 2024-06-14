from pathlib import Path
from typing import Annotated

import trio
from hypercorn.trio import serve
from hypercorn.config import Config as HyperConfig

from fused_local.app import app, setup_static_serving
from fused_local.local_certs import generate_certs
import fused_local.config

import typer

# TODO: we can't easily serve HTTP/2 over localhost, because it requires HTTPS.
# The browser won't trust our self-signed certificates, which isn't great UX.
# See https://freedium.cfd/https://levelup.gitconnected.com/deploy-fastapi-with-hypercorn-http-2-asgi-8cfc304e9e7a
# But the speedup is rather nice.

cli = typer.Typer()


@cli.command()
def main(
    code_path: Annotated[
        Path, typer.Argument(help="Local .py script to watch and render")
    ],
    open: Annotated[
        bool, typer.Option(help="Open the map in the default browser")
    ] = True,
    dev: Annotated[
        bool,
        typer.Option(
            help="Enable hot-reloading of frontend code, disable HTTP/2 and TLS"
        ),
    ] = False,
):
    """Code to map, instantly.

    Write code in a .py file. Annotate functions with ``@fused_local.tile`` that take a
    `GeoBox`. Fused will open an interactive map in your browser where that function
    gets re-run as you move around the map.
    """
    protocol = "http" if dev else "https"
    host = "127.0.0.1:8000"

    fused_local.config._config = fused_local.config.Config(
        dev=dev, user_code_path=code_path, url=f"{protocol}://{host}", open_browser=open
    )

    hyper_config = HyperConfig()
    hyper_config.bind = [host]
    # config.accesslog = "-"
    # config.errorlog = "-"

    if not dev:
        # TODO base on path of file we're serving?
        # better yet, store in the cache?
        key_file = Path.cwd() / "key.pem"
        cert_file = Path.cwd() / "cert.pem"

        if not key_file.exists() or not cert_file.exists():
            print(f"Generating self-signed certificate to {key_file} and {cert_file}")
            generate_certs(key_file, cert_file)

        # FIXME re-enable HTTPS so we can use HTTP/2
        # websockets seem to break in hypercorn with http2, though.
        hyper_config.keyfile = str(key_file)
        hyper_config.certfile = str(cert_file)

    # TODO anyio?: https://github.com/pgjones/hypercorn/issues/184#issuecomment-1943483328

    setup_static_serving()
    trio.run(serve, app, hyper_config)


if __name__ == "__main__":
    cli()
