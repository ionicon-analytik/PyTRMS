import os
import doctest

optionflags = (0
    | doctest.FAIL_FAST
)

base_dir = os.path.join(os.path.dirname(__file__), '..')

def test_README_docstrings():
    FUT = os.path.join(base_dir, 'README.md')
    assert os.path.exists(FUT)
    doctest_result = doctest.testfile(FUT, optionflags=optionflags)
    assert doctest_result.failed == 0, f"{FUT}: doctests have failed"


if __name__ == '__main__':
    test_README_docstrings()

