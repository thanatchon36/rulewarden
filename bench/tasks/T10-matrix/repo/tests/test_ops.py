from matrix import determinant


def test_det_2x2():
    assert determinant([[1, 2], [3, 4]]) == -2
