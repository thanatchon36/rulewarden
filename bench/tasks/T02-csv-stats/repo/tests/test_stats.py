from csvstats import column_stats


def test_simple(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("a,b\n1,x\n3,y\n")
    s = column_stats(p, "a")
    assert s["count"] == 2 and s["mean"] == 2.0
