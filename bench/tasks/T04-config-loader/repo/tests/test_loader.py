from appconfig import load_config


def test_reads_section(tmp_path):
    p = tmp_path / "app.ini"
    p.write_text("[server]\nhost = localhost\n")
    assert load_config(p, env={})["server"]["host"] == "localhost"
