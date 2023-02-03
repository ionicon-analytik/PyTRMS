"""Test of module pytrms.modbus

"""
import pytest

import struct

import pytrms.modbus
from pytrms.modbus import _pack, _unpack

@pytest.fixture
def connection():
     con = pytrms.modbus.IoniconModbus('localhost', 502)
     yield con
     con.close()


class TestIoniconModbus:

    def test_unpack_converts_registers(self):
        assert _unpack([17448, 0], 'float') == 672.
        assert _unpack([17446, 32768], 'float') == 666.
        assert _unpack([16875, 61191, 54426, 37896], 'double') == 3749199524.83057
        assert _unpack([16875, 61191, 54426, 37896], 'long') == 4750153048903029768

    def test_unpack_fails_with_nonsensical_arguments(self):
        with pytest.raises(struct.error):
            _unpack([16875, 61191, 54426, 37896], 'float')

        with pytest.raises(struct.error):
            _unpack([17446, 32768], 'long')

    @pytest.mark.parametrize('c_type', [
        'int',
        'float',
        'long',
        'double',
    ])
    def test_pack(self, c_type):
        assert _unpack(_pack(42, c_type), c_type) == 42

    def test_available_keys(self, connection):
        assert len(connection.available_keys) > 0

    def test_read_key(self, connection):
        assert len(connection.read_key('foo')) > 0

    def test_read_all(self, connection):
        assert len(connection.read_all()) > 0

    def test_n_masses(self, connection):
        assert connection.n_masses > 0

