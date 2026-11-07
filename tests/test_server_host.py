"""The server listens on this computer only unless told otherwise, and says so loudly when it does not (the viewer API has no login)."""
import sys
import pytest
from caitanya import server


@pytest.fixture
def captured(monkeypatch, tmp_path):
    import uvicorn
    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, host=None, port=None, **kw: seen.update(host=host, port=port))

    def run(*extra):
        monkeypatch.setattr(sys, "argv", ["caitanya.server", "--population", "2", "--width", "64", "--depth", "64", "--run-dir", str(tmp_path / f"r{len(extra)}"), *extra])
        server.main()
        return seen
    return run


def test_the_default_is_this_computer_only(captured, capsys):
    assert captured()["host"] == "127.0.0.1"
    assert "WARNING" not in capsys.readouterr().out


def test_another_address_is_used_and_a_warning_is_printed(captured, capsys):
    assert captured("--host", "100.64.0.5")["host"] == "100.64.0.5"
    out = capsys.readouterr().out
    assert "WARNING" in out and "100.64.0.5" in out and "read-only" in out


def test_the_option_exists_and_defaults_to_local():
    assert server.build_parser().parse_args([]).host == "127.0.0.1"
