import math

import pytest

from csvstats import column_stats


def write(tmp_path, text):
    p = tmp_path / "data.csv"
    p.write_text(text, encoding="utf-8")
    return p


def test_full_stats(tmp_path):
    p = write(tmp_path, "name,score\nann,10\nbob,20\ncy,30\ndee,40\n")
    s = column_stats(p, "score")
    assert s["count"] == 4 and isinstance(s["count"], int)
    assert s["mean"] == 25.0 and s["median"] == 25.0
    assert s["min"] == 10.0 and s["max"] == 40.0
    assert math.isclose(s["stdev"], 12.909944487358056)


def test_blanks_ignored_and_quotes(tmp_path):
    p = write(tmp_path, 'id,"value, raw"\n1," 2.5 "\n2,\n3,  \n4,"-1"\n')
    s = column_stats(p, "value, raw")
    assert s["count"] == 2 and s["min"] == -1.0 and s["max"] == 2.5


def test_single_value_stdev_zero(tmp_path):
    s = column_stats(write(tmp_path, "x\n7\n"), "x")
    assert s["stdev"] == 0.0 and s["median"] == 7.0


def test_missing_column(tmp_path):
    with pytest.raises(KeyError):
        column_stats(write(tmp_path, "x\n1\n"), "y")


def test_non_numeric_names_row(tmp_path):
    with pytest.raises(ValueError, match="3"):
        column_stats(write(tmp_path, "x\n1\n2\nabc\n"), "x")


def test_empty_column(tmp_path):
    with pytest.raises(ValueError):
        column_stats(write(tmp_path, "x,y\n,1\n,2\n"), "x")


def test_accepts_str_path(tmp_path):
    p = write(tmp_path, "x\n1\n2\n3\n")
    assert column_stats(str(p), "x")["median"] == 2.0
