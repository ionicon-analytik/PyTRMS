from abc import abstractmethod
from collections.abc import Iterable
from functools import partial, lru_cache

import h5py
import pandas as pd

from .helpers import convert_labview_to_posix


class H5Reader(Iterable):

    @property
    def timezero(self):
        return convert_labview_to_posix(float(self.hf.attrs['FileCreatedTime_UTC']))

    def __init__(self, path):
        self.path = path
        self.hf = h5py.File(path, 'r')

    def __iter__(self):
        # TODO :: optimize: gib eine 'smarte' Series zurueck, die sich die aufgerufenen
        # columns merkt! diese haelt die ganze erste Zeile des datensatzes. 
        # ab dem zweiten durchgang kann die Series auf diese columns
        # reduziert werden
        traces = self.get_traces()
        addtraces = self.get_addtraces()
        combined = pd.concat([traces, addtraces], axis='columns')

        return combined.iterrows()

    def print_all(self):
        """Look for data-info traces."""
    
        def func(object_name):
            # defines a 'visit'-function that removes matched sections one by one
            print(object_name)
            return None
    
        self.hf.visit(func)
    
    def locate_datainfo(self):
        """Look for data-info traces."""
        dataloc = set()
        infoloc = set()
    
        def func(object_name):
            # defines a 'visit'-function that removes matched sections one by one
            nonlocal dataloc
            nonlocal infoloc
            if object_name.endswith('/Data'):
                dataloc |= {object_name[:-5], }
            if object_name.endswith('/Info'):
                infoloc |= {object_name[:-5], }
            return None
    
        self.hf.visit(func)
    
        return dataloc.intersection(infoloc)
    
    def read_datainfo(self, groupname):
        group = self.hf[groupname]
        data = group['Data']
        info = group['Info']
        names = [b.decode('latin1') for b in info[0,:]]
    
        return pd.DataFrame(data, columns=names)
    
    def get_addtraces(self):
        frames = []
        for loc in self.locate_datainfo():
            frames.append(self.read_datainfo(loc))
    
        return pd.concat(frames, axis='columns')
    
    def get_traces(self, kind='raw', force_original=False):
        tracedata = self.hf.get('PROCESSED/TraceData')
        lut = {
            'con': 'ConcentrationsData',
            'raw': 'RawData',
            'cor': 'CorrectedData',
        }
        if tracedata is None:
            tracedata = self.hf['TRACEdata']
            lut = {
                'con': 'TraceConcentration',
                'raw': 'TraceRaw',
                'cor': 'TraceCorrected',
            }

        loc = lut[kind[:3].lower()]
        try:
            data = tracedata[loc]
        except KeyError as exc:
            msg = ("Unknown trace-type! `kind` must be one of 'raw', 'corrected' or "
                   "'concentration'.")
            raise KeyError(msg) from exc
    
        info = self.hf['TRACEdata/TraceInfo']
        labels = [b.decode('latin1') for b in info[1,:]]
    
        return pd.DataFrame(data, columns=labels)

    @lru_cache
    def get_all(self, kind='raw', index='abs_cycle', force_original=False):
        frame = pd.concat([self.get_traces(kind, force_original), self.get_addtraces()], axis='columns')
        frame.index = self.get_index(index)

        return frame

    def get_index(self, kind='abs_cycle'):
        lut = {
                'REL_CYCLE': (0, lambda a: a.astype('int', copy=False)),
                'ABS_CYCLE': (1, lambda a: a.astype('int', copy=False)),
                'ABS_TIME': (2, lambda a: list(map(convert_labview_to_posix, a))),
                'REL_TIME': (3, lambda a: list(map(partial(pd.Timedelta, unit='s'), a))),
        }
        info = self.hf['SPECdata/Times']
        try:
            _N, convert = lut[kind.upper()]
        except KeyError as exc:
            msg = "Unknown index-type! `kind` must be one of {0}.".format(', '.join(lut.keys()))
            raise KeyError(msg) from exc
    
        index = info[:, _N]
    
        return convert(index)
    
