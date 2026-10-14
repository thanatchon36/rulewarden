from mdtoc import toc


def test_single():
    assert toc("# Title\n") == "- [Title](#title)\n"
