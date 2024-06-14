import math
import anyio
from starlette.types import ASGIApp, Scope, Receive, Send


class CancelOnDisconnectMiddleware:
    "Cancel the request handler if the HTTP client cancels the request"

    # Based roughly on https://github.com/tiangolo/fastapi/discussions/11360#discussion-6427734
    # but converted to anyio (and therefore to not leak tasks everywhere).

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Use a channel to take ASGI messages in from `receive`, peek at them,
        # and forward on to `app`.
        # TODO: what should the buffer size be? 0 blocks on send, 1 seems to work,
        # inf seems 'safe', but maybe is wrong?
        chan_in, chan_out = anyio.create_memory_object_stream(math.inf)

        async def feed_app():
            async with chan_out:
                # when `self.app` finishes, closes `chan_out` so on the send side knows to stop
                await self.app(scope, chan_out.receive, send)

        async with anyio.create_task_group() as tg:
            tg.start_soon(feed_app)

            with chan_in:
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        # TODO use closure of the channel to cancel the `self.app` task instead?
                        tg.cancel_scope.cancel()
                        break
                    try:
                        await chan_in.send(message)
                    except anyio.BrokenResourceError:
                        # `self.app` has completed, closing `chan_out`
                        break


if __name__ == "__main__":
    from fastapi import FastAPI
    import uvicorn

    app = FastAPI()
    app.add_middleware(CancelOnDisconnectMiddleware)

    @app.get("/")
    async def root():
        print("request")
        try:
            await anyio.sleep(10)
        except anyio.get_cancelled_exc_class():
            print("was cancelled")
            raise

        print("not cancelled")

        return {"message": "Tomato"}

    try:
        uvicorn.run(app)
    except KeyboardInterrupt:
        pass
    # try `curl http://127.0.0.1:8000`, then ctrl-c before it completes.
    # should print "was cancelled".
    # if you comment out the `add_middleware` line, you'll get "not cancelled" after 10s.
