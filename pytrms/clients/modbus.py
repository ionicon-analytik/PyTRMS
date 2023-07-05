"""Module modbus.py

"""
import os
import logging
import struct
import json  # legacy mode(?)
from collections import namedtuple

from pyModbusTCP import client

log = logging.getLogger(__name__)

_root = os.path.abspath(os.path.dirname(__file__))
_par_id_list = os.path.join(_root, 'data', 'par_ID_list.txt')

with open(_par_id_list) as f:
    it = iter(f)
    assert next(it) == 'ID\tName\n', 'Modbus parameter file %s is corrupt!' % _par_id_list
    _id_to_descr = {int(id_): name for id_, name in (line.strip().split('\t') for line in it)}

__all__ = ['IoniconModbus']


class IoniconModbus:
    _template = namedtuple('Parameter', ('Set', 'Act', 'Id', 'State'))

    @staticmethod
    def _unpack(registers):
        """Convert registers to float/double value.

        Two 8-bit register are converted to one float value.
        Four 8-bit register are converted to one double value.
        """
        if len(registers) == 2:
            return struct.unpack('>f', struct.pack('>HH', *registers))[0]
        if len(registers) == 4:
            return struct.unpack('>d', struct.pack('>HHHH', *registers))[0]
        raise ValueError("unpack requires a buffer of 2 or 4 bytes")

    @staticmethod
    def _pack(value, bytes_=2):
        """Convert floating point 'value' to registers.

        One float value is packed into two or four 8-bit registers, 
        depending on the number of 'bytes_'.
        """
        if bytes_ == 2:
            return struct.unpack('>HH', struct.pack('>f', value))
        if bytes_ == 4:
            return struct.unpack('>HHHH', struct.pack('>d', value))
        raise ValueError("pack requires a buffer of 2 or 4 bytes")

    def __init__(self, host='localhost', port=502):
        self.mc = client.ModbusClient(host=host, port=port)
        if not self.mc.open():
            raise IOError("Cannot connect to modbus socket @ %s:%d!" % (str(host), port))
        self._addresses = {}

    @property
    def available_keys(self):
        if not self._addresses:
            self.read_all()

        return set(self._addresses.keys())

    def read_all(self):
        if not self.mc.is_open:
            self.mc.open()
        rv = {}
        for offset in range(2001, 3900, 120):
            input_regs = self.mc.read_input_registers(offset, 120)
            for addr in range(0, 120, 6):
                par_id, set1, set2, act1, act2, state = input_regs[addr:addr+6]
                try:
                    descr = _id_to_descr[par_id]
                except KeyError as exc:
                    log.error("par Id %d @ register %d not in par_ID_list!" % (par_id, addr+offset))
                    continue

                vset = self._unpack((set1, set2))
                vact = self._unpack((act1, act2))
                rv[descr] = self._template(vset, vact, par_id, state)
                self._addresses[descr] = addr+offset

        return rv

    @propery
    def n_masses(self):
        return int(self.read_reg(8000))

    def get_traces(self, use_raw=False):
        if not self.mc.is_open:
            self.mc.open()
        if use_raw:
            offset = 4000
        else:  # use conc
            offset = 6000
        rv = {}
        n_masses = int(self.read_reg(8000))
        for addr in range(n_masses):
            mass = self.read_reg(8002+addr)
            data = self.read_reg(offset+14+addr)
            key = "{0:.4}".format(mass)
            rv[key] = data

        #return json.dumps(rv)  # legacy mode(?)
        return rv

    def read_reg(self, addr, bytes_=2):
        input_reg = self.mc.read_input_registers(addr, bytes_)

        return self._unpack(input_reg)

    def read(self, key):
        if not self._addresses:
            self.read_all()

        addr = self._addresses[key]
        input_reg = self.mc.read_input_registers(addr, 6)
        par_id, set1, set2, act1, act2, state = input_reg
        vset = self._unpack((set1, set2))
        vact = self._unpack((act1, act2))

        return self._template(vset, vact, par_id, state)

