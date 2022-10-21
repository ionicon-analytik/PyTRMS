"""Test of module pytrms.modbus

"""
import sys, os
from os.path import abspath, join, dirname
import platform
import pytest
from unittest.mock import *

import logging
import itertools
from numpy import array
from numpy.testing import assert_allclose

sys.path.insert(0, abspath(join(dirname(__file__), '..')))
sys.path.insert(0, abspath(join(dirname(__file__), '..', 'pytrms')))


from pytrms.modbus import IoniconModbus


class TestIoniconModbus:

    def test_unpack(self):
        assert IoniconModbus._unpack([17448, 0]) == 672
        assert IoniconModbus._unpack([17446, 32768]) == 666

        assert IoniconModbus._unpack([16875, 61191, 54426, 37896]) == 3749199524.83057

        with pytest.raises():
            IoniconModbus._unpack([17446])

        with pytest.raises():
            IoniconModbus._unpack([17, 44, 6])

    def test_pack(self):
        assert IoniconModbus._unpack(IoniconModbus._pack(42)) == 42


