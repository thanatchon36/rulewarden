import pytest

from appconfig import load_config

INI = """
[DEFAULT]
debug = no

[server]
host = ${HOST}
port = 8080
ratio = 0.75
enabled = Yes
name =   web 1  
price = $$5

[db]
url = postgres://${DB_USER}@db/app
debug = on
"""


def write(tmp_path, text=INI):
    p = tmp_path / "app.ini"
    p.write_text(text)
    return p


def test_types_interpolation_and_defaults(tmp_path):
    cfg = load_config(write(tmp_path), env={"HOST": "example.org", "DB_USER": "ann"})
    assert set(cfg) == {"server", "db"}
    s = cfg["server"]
    assert s["host"] == "example.org" and s["port"] == 8080 and isinstance(s["port"], int)
    assert s["ratio"] == 0.75 and s["enabled"] is True and s["debug"] is False
    assert s["name"] == "web 1" and s["price"] == "$5"
    assert cfg["db"]["url"] == "postgres://ann@db/app" and cfg["db"]["debug"] is True


def test_env_override(tmp_path):
    env = {"HOST": "h", "DB_USER": "u", "APP_SERVER_PORT": "9090", "APP_DB_URL": "sqlite://"}
    cfg = load_config(str(write(tmp_path)), env=env)
    assert cfg["server"]["port"] == 9090 and cfg["db"]["url"] == "sqlite://"


def test_override_skips_interpolation_of_file_value(tmp_path):
    cfg = load_config(write(tmp_path), env={"DB_USER": "u", "APP_SERVER_HOST": "over"})
    assert cfg["server"]["host"] == "over"


def test_missing_variable(tmp_path):
    with pytest.raises(KeyError, match="DB_USER"):
        load_config(write(tmp_path), env={"HOST": "h"})


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.ini", env={})


def test_no_code_execution(tmp_path):
    p = write(tmp_path, "[x]\nv = __import__('os').getcwd()\nw = [1, 2]\n")
    cfg = load_config(p, env={})
    assert cfg["x"]["v"] == "__import__('os').getcwd()" and cfg["x"]["w"] == "[1, 2]"


def test_default_env_is_os_environ(tmp_path, monkeypatch):
    monkeypatch.setenv("HOST", "from-os")
    monkeypatch.setenv("DB_USER", "x")
    assert load_config(write(tmp_path))["server"]["host"] == "from-os"
