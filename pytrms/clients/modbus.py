"""Module modbus.py

"""
import os
import logging
import struct
import json  # TODO :: legacy mode(?)
from collections import namedtuple

from pyModbusTCP import client

log = logging.getLogger(__name__)

__all__ = ['IoniconModbus']


_root = os.path.abspath(os.path.dirname(__file__))
_par_id_list = os.path.join(_root, 'data', 'par_ID_list.txt')

with open(_par_id_list) as f:
    it = iter(f)
    assert next(it) == 'ID\tName\n', 'Modbus parameter file %s is corrupt!' % _par_id_list
    _id_to_descr = {int(id_): name for id_, name in (line.strip().split('\t') for line in it)}


def _unpack(registers, c_type='float'):
    """Convert a list of register values to a numeric Python value.

    Depending on 'c_type', the value is packed into two or four
    8-bit registers, for 2-byte (single) and 4-byte (double)
    representation, respectively.
    """
    if c_type == 'float':
        return struct.unpack('>f', struct.pack('>HH', *registers))[0]
    if c_type == 'double':
        return struct.unpack('>d', struct.pack('>HHHH', *registers))[0]
    if c_type == 'int':
        return struct.unpack('>i', struct.pack('>HH', *registers))[0]
    if c_type == 'long':
        return struct.unpack('>q', struct.pack('>HHHH', *registers))[0]
    raise ValueError("unknown C-type (%s)" % c_type)

def _pack(value, c_type='float'):
    """Convert floating point 'value' to registers.

    Depending on 'c_type', the value is packed into two or four
    8-bit registers, for 2-byte (single) and 4-byte (double)
    representation, respectively.
    """
    if c_type == 'float':
        return struct.unpack('>HH', struct.pack('>f', value))
    if c_type == 'double':
        return struct.unpack('>HHHH', struct.pack('>d', value))
    if c_type == 'int':
        return struct.unpack('>HH', struct.pack('>i', value))
    if c_type == 'long':
        return struct.unpack('>HHHH', struct.pack('>q', value))
    raise ValueError("unknown C-type (%s)" % c_type)


class IoniconModbus:
    _template = namedtuple('Parameter', ('Set', 'Act', 'Id', 'State'))

    def _read_reg(self, addr, c_type):
        if c_type in ['float', 'int']:
            n_bytes = 2
        elif c_type in ['double', 'long']:
            n_bytes = 4
        else:
            raise ValueError("unknown C-type (%s)" % c_type)

        input_reg = self.mc.read_input_registers(addr, n_bytes)

        return _unpack(input_reg, c_type)

    def __init__(self, host='localhost', port=502):
        self.mc = client.ModbusClient(host=host, port=port)
        if not self.mc.open():
            raise IOError("Cannot connect to modbus socket @ %s:%d!" % (str(host), port))
        self._addresses = {}

    def close(self):
        if self.mc.open():
            self.mc.close()

    def __del__(self):
        self.close()

    @property
    def n_masses(self):
        return int(self._read_reg(8000, 'int'))

    @property
    def available_keys(self):
        if not self._addresses:
            self.read_all()

        return set(self._addresses.keys())

    def read_key(self, key):
        if not self._addresses:
            self.read_all()

        addr = self._addresses[key]
        input_reg = self.mc.read_input_registers(addr, 6)
        par_id, set1, set2, act1, act2, state = input_reg
        vset = _unpack((set1, set2))
        vact = _unpack((act1, act2))

        return self._template(vset, vact, par_id, state)

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

                vset = _unpack((set1, set2))
                vact = _unpack((act1, act2))
                rv[descr] = self._template(vset, vact, par_id, state)
                self._addresses[descr] = addr+offset

        return rv

    def get_traces(self, use_raw=False):
        if not self.mc.is_open:
            self.mc.open()
        if use_raw:
            offset = 4000
        else:  # use conc  TODO :: whatabout corr??    
            offset = 6000
        rv = {}
        n_masses = int(self._read_reg(8000, 'int'))
        for addr in range(n_masses):
            mass = self._read_reg(8002+addr, 'float')
            data = self._read_reg(offset+14+addr, 'float')
            key = "{0:.4}".format(mass)
            rv[key] = data

        #return json.dumps(rv)  # TODO :: legacy mode(?)
        return rv

