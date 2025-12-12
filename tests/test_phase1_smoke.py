from moaa_prime.core.app import MoAAPrime

def test_phase1_smoke_hello():
    app = MoAAPrime()
    assert "hello" in app.hello().lower()
