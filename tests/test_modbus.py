"""Test of module pytrms.clients.modbus

"""
import pytest

import struct

import pytrms.clients.modbus
from pytrms.clients.modbus import _pack, _unpack


class TestIoniconModbus:

    def test_unpack_converts_registers(self):
        assert _unpack([17448, 0], 'float') == 672.
        assert _unpack([17446, 32768], 'float') == 666.
        assert _unpack([16875, 61191, 54426, 37896], 'double') == 3749199524.83057
        assert _unpack([16875, 61191, 54426, 37896], 'long') == 4750153048903029768

    def test_unpack_fails_with_nonsensical_arguments(self):
        with pytest.raises(AssertionError):
            _unpack([16875, 61191, 54426, 37896], 'float')

        with pytest.raises(AssertionError):
            _unpack([17446, 32768], 'long')

    @pytest.mark.parametrize('c_type', [
        'int',
        'float',
        'long',
        'double',
    ])
    def test_pack(self, c_type):
        assert _unpack(_pack(42, c_type), c_type) == 42


