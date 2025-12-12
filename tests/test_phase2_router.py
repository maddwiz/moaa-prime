from moaa_prime.core.app import MoAAPrime


def test_routes_math():
    app = MoAAPrime()
    out = app.run_once("Solve 2x + 3 = 7")
    assert out["decision"]["agent"] == "math-agent"


def test_routes_code():
    app = MoAAPrime()
    out = app.run_once("My python code has a bug in this function")
    assert out["decision"]["agent"] == "code-agent"
