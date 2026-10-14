from resilience import retry


def test_success_first_try():
    @retry(3)
    def ok():
        return 1

    assert ok() == 1
