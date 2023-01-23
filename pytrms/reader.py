from abc import abstractmethod
from collections.abc import Iterable
from functools import partial, lru_cache

import h5py
import pandas as pd

# make this file %run'nable from IPython:
try:
    from .helpers import convert_labview_to_posix
except ImportError:  # attempted relative import with no known parent package
    from pytrms.helpers import convert_labview_to_posix


class GroupNotFoundError(KeyError):
    pass


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
    
    def _read_datainfo(self, group, prefix=''):
        # parse a "Data-Info" group into a pd.DataFrame
        # 'group' may be a hdf5 group or a string-location to a group
        if isinstance(group, str):
            group = self.hf[group]
        data = group[prefix + 'Data']
        info = group[prefix + 'Info']
        if info.ndim > 1:
            info = info[0,:]
        if hasattr(info[0], 'decode'):
            info = [b.decode('latin1') for b in info]
    
        return pd.DataFrame(data, columns=info)
    
    def get_addtraces(self):
        frames = []
        for loc in self.locate_datainfo():
            frames.append(self._read_datainfo(loc))
    
        return pd.concat(frames, axis='columns')
    
    def get_traces(self, kind='raw', force_original=False):
        if force_original:
            return self._read_traces(kind)
        else:
            try:
                return self._read_processed_traces(kind)
            except GroupNotFoundError:
                return self._read_traces(kind)

    def _read_processed_traces(self, kind):
        # error conditions:
        # 1) 'kind' is not recognized -> ValueError
        # 2) no 'PROCESSED/TraceData' group -> GroupNotFoundError
        # 3) expected group not found -> KeyError (file is not supported yet)
        lut = {
            'con': 'Concentrations',
            'raw': 'Raw',
            'cor': 'Corrected',
        }
        tracedata = self.hf.get('PROCESSED/TraceData')
        if tracedata is None:
            raise GroupNotFoundError()

        try:
            prefix = lut[kind[:3].lower()]
        except KeyError as exc:
            msg = ("Unknown trace-type! `kind` must be one of 'raw', 'corrected' or 'concentration'.")
            raise ValueError(msg) from exc

        try:
            data = self._read_datainfo(tracedata, prefix=prefix)  # may raise KeyError
            pt = self._read_datainfo(tracedata, prefix='PeakTable')  # may raise KeyError
            labels = [b.decode('latin1') for b in pt['label']]
        except KeyError as exc:
            raise KeyError(f'unknown group {exc}. filetype is not supported yet.') from exc

        mapper = dict(zip(data.columns, labels))
        data.rename(columns=mapper)

        return data

    def _read_traces(self, kind):
        lut = {
            'con': 'TraceConcentration',
            'raw': 'TraceRaw',
            'cor': 'TraceCorrected',
        }
        tracedata = self.hf['TRACEdata']
        try:
            loc = lut[kind[:3].lower()]
            data = tracedata[loc]
        except KeyError as exc:
            msg = ("Unknown trace-type! `kind` must be one of 'raw', 'corrected' or 'concentration'.")
            raise ValueError(msg) from exc
    
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
    
