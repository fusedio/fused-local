import anyio
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
# from fused_local.cancellation_middleware import CancelOnDisconnectMiddleware

pytest.mark.skip(reason="Test doesn't work")

app = FastAPI()
# app.add_middleware(CancelOnDisconnectMiddleware)

was_cancelled = False


@app.get("/")
async def root():
    global was_cancelled
    try:
        await anyio.sleep(1)
    except anyio.get_cancelled_exc_class():
        was_cancelled = True
        raise

    return {"message": "Tomato"}


def test_cancellation():
    client = TestClient(app, backend="trio")
    with pytest.raises(httpx.TimeoutException):
        # FIXME the timeout simply doesn't do anything!
        client.get("/", timeout=0.05)

    assert was_cancelled
