import datetime
import decimal
import pathlib
from functools import partial
import sys

import fused_local
import pytest
from fused_local.hash import tokenize
from odc.geo.geobox import GeoBox


class CallMeMaybe:
    def __call__(self):
        return 1


@pytest.mark.parametrize(
    "constructor, expected",
    zip(
        [
            lambda: 1,
            lambda: 1.0,
            lambda: "foo",
            lambda: b"foo",
            lambda: None,
            lambda: Ellipsis,
            lambda: slice(1, 2),
            lambda: complex(1, 2),
            lambda: decimal.Decimal("1.0"),
            lambda: datetime.date(2021, 1, 1),
            lambda: datetime.time(1, 2, 3),
            lambda: datetime.datetime(2021, 1, 1, 1, 2, 3),
            lambda: datetime.timedelta(days=1),
            lambda: pathlib.PurePath("/foo"),
            lambda: [1, 2],
            lambda: {"foo": 1},
            lambda: {1, 2},
            lambda: partial(lambda x: x, 1),
            lambda: exec,
            lambda: pathlib,
            lambda: fused_local,
            lambda: CallMeMaybe(),
            lambda: GeoBox.from_bbox((0, 0, 1, 1), "EPSG:4326", resolution=0.1),
        ],
        [
            # NOTE: hardcode the hashes to ensure stability across restarts.
            # obviously when the implementation changes, update this as needed.
            "6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b",
            "d0ff5974b6aa52cf562bea5921840c032a860a91a3512f7fe8f768f6bbe005f6",
            "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
            "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
            "dc937b59892604f5a86ac96936cd7ff09e25f18ae6b758e8014a24c7fa039e91",
            "4637e99b28a1ce112e8f4009dbf144f3a75a04d3e4b0c30b084aef21c5e3cfe6",
            "d6c909b3ac94a44d71f32c054cb4bb38b3965c81e5899e04aad7a3f4d4d6eb8f",
            "a8400f1c19a4630c1bfb794a66c5d60ee57cb4ffcf8c14047a8bb2ae09a289b2",
            "d0ff5974b6aa52cf562bea5921840c032a860a91a3512f7fe8f768f6bbe005f6",
            "5639fe065f49530b4b9c3a3a6815e996d357fda6acf10d133bc2c81f244ef9fd",
            "90b3ce2bd06ddb211cd6fe70fa3a32e819fb8ebf3fb00394b5b3abdce60ab96e",
            "f5d48967f47b23852f3aac7bc6ff64170513a88f2112fd5542692b0fa6492854",
            "5f140c96a34b89e8fd732d3b25094ce20c900a663e55e7d1ca6461be346501f2",
            "6f64c6e6261f492ac220b0a4cd9a14c6373181b92a4a8040c1fcde5db31ffc94",
            "0de29f28705aca2ba9a8b12f11dd264a4a2249b2b5e1ada9d08ca1a2cb127e1d",
            "e8798263438c84acf30068f517f8ccd3984c50b5a5a564fe7f4b14a43c50ae1a",
            "78b834079a24bb82de91531f87f7f68790cf71fc750c0bce89dce45e28122cd4",
            "8376056fa88ef0c63ccdaef810de9e6d74f02457c02ae62977425f689973488c",
            "811461a03c69f6780151a0ec56e9d815fa4208d6ebe4dc163c69f36880cb9f2e",
            "bc55788fc07834cf49a1df1e9dc29ab2650291566e019d38ec17f3ebbded5146",
            "3d3fd83e3329a7158557bb6f28032bc8a59e029474001ef7579f9ac5c803f248",
            "41dccb521c5e55cbc84b9600bb64fba3f093f359e8a67700f850ced833a1a237",
            "f088cb33d1ff8be4d1c392d2c92a66323ceb26ef565aeccfd6def400a7a9408f",
        ],
    ),
)
def test_tokenize(constructor, expected):
    a = constructor()
    b = constructor()

    ta = tokenize(a)
    tb = tokenize(b)

    # used for getting the hashes to hardcode in the test.
    # run with `pytest -s 1>/dev/null`, then copy-paste in with multi-line editing
    print(ta, file=sys.stderr)
    assert ta == tb, a
    assert ta == expected, a


def test_tokenize_func():
    def f(x):  # type: ignore
        return x

    t1 = tokenize(f)

    def f(x):
        return x

    t2 = tokenize(f)

    def g(x):
        return x

    t3 = tokenize(f)

    # in our case, we don't actually care about the name, just the body.
    # I think.
    # Maybe?
    assert (
        t1
        == t2
        == t3
        # NOTE: hardcode the hash to ensure stability across restarts.
        # obviously when the implementation changes, update this as needed.
        == "cbe9f68445c25a848d3256d5809c9308b7f272bbb2e4dfc55e6fd878d0523e8e"
    )


def test_tokenize_func_closure():
    x = 1

    def f():  # type: ignore
        return x

    t1 = tokenize(f)

    x = 2

    def f():
        return x

    t2 = tokenize(f)

    assert t1 != t2


def test_tokenize_func_defaults():
    def f1(x=1):
        return x

    def f2(x=2):
        return x

    assert tokenize(f1) != tokenize(f2)


GLOBAL_VAR = 0


def test_tokenize_func_globals():
    def f():  # type: ignore
        return GLOBAL_VAR

    t1 = tokenize(f)

    global GLOBAL_VAR
    GLOBAL_VAR = 1

    def f():
        return GLOBAL_VAR

    t2 = tokenize(f)

    assert t1 != t2
