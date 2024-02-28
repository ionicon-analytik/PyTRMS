"""file h5reader.py

"""
from functools import partial, lru_cache

import h5py
import pandas as pd

__all__ = ['H5Reader']

def convert_labview_to_posix(ts):
    '''Create a `Pandas.Timestamp` from LabView time.'''
    posix_time = ts - 2082844800

    return pd.Timestamp(posix_time, unit='s')

class GroupNotFoundError(KeyError):
    pass


class H5Reader:

    @property
    def timezero(self):
        return convert_labview_to_posix(float(self.hf.attrs['FileCreatedTime_UTC']))

    @property
    def inst_type(self):
        return str(self.hf.attrs.get('InstrumentType', [b'',])[0].decode('latin-1'))

    @property
    def sub_type(self):
        return str(self.hf.attrs.get('InstSubType', [b'',])[0].decode('latin-1'))

    @property
    def serial(self):
        return str(self.hf.attrs.get('InstSerial#', [b'',])[0].decode('latin-1'))

    @serial.setter
    def serial(self, number):
        self.hf.attrs['InstSerial#'] = np.array([str(number).encode()], dtype='S')
        self.hf.flush()

    def __init__(self, path):
        self.path = path
        self.hf = h5py.File(path, 'r', swmr=True)

    def read_addtraces(self, matches=None, index='abs_cycle'):
        """Reads all /AddTraces into a DataFrame.

        - 'index' one of abs_cycle|abs_time|rel_cycle|rel_time
        """
        if matches is not None:
            if callable(matches):
                filter_fun = matches
            elif isinstance(matches, str):
                filter_fun = lambda x: matches.lower() in x.lower()
            else:
                raise ValueError(repr(matches))
            locs = list(filter(filter_fun, self._locate_datainfo()))
        else:
            locs = self._locate_datainfo()

        if not len(locs):
            raise ValueError(f"no match for {matches} in {self._locate_datainfo()}")

        rv = pd.concat((self._read_datainfo(loc) for loc in locs), axis='columns')
        rv.index = self.read_index(index)

        # de-duplicate trace-columns to prevent issues...
        return rv.loc[:, ~rv.columns.duplicated()]

    def read_calctraces(self, index='abs_cycle'):
        """Reads the calculated traces into a DataFrame.

        - 'index' one of abs_cycle|abs_time|rel_cycle|rel_time
        """
        return self.read_addtraces('CalcTraces', index)

    def read_traces(self, kind='conc', index='abs_cycle', force_original=False):
        """Reads the traces of the given 'kind' into a DataFrame.

        - 'kind' one of raw|corr|conc
        - 'index' one of abs_cycle|abs_time|rel_cycle|rel_time
        - 'force_original' ignore the post-processed data
        """
        if force_original:
            return self._read_original_traces(kind, index)
        else:
            try:
                return self._read_processed_traces(kind, index)
            except GroupNotFoundError:
                return self._read_original_traces(kind, index)

    @lru_cache
    def read_all(self, kind='conc', index='abs_cycle', force_original=False):
        # ...and throw it all together:
        return pd.concat([
            self.read_traces(kind, index, force_original),
            self.read_addtraces(None, index),
        ], axis='columns')

    def read_index(self, kind='abs_cycle'):
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
    
        return convert(info[:, _N])
    
    def __iter__(self):
        # TODO :: optimize: gib eine 'smarte' Series zurueck, die sich die aufgerufenen
        # columns merkt! diese haelt die ganze erste Zeile des datensatzes. 
        # ab dem zweiten durchgang kann die Series auf diese columns
        # reduziert werden
        return self.read_all().iterrows()

    def print_datastructure(self):
        """Prints all hdf5 group- and dataset-names to stdout."""
        # this walks all h5 objects in alphabetic order:
        self.hf.visit(lambda obj_name: print(obj_name))
    
    def __repr__(self):
        return "<%s %s [no. %s]>" % (self.inst_type, self.sub_type, self.serial)

    @lru_cache
    def _locate_datainfo(self):
        """Lookup groups with data-info traces."""
        dataloc = set()
        infoloc = set()
    
        def func(object_name):
            nonlocal dataloc
            nonlocal infoloc
            if object_name.endswith('/Data'):
                dataloc |= {object_name[:-5], }
            if object_name.endswith('/Info'):
                infoloc |= {object_name[:-5], }
            return None
    
        # use the above 'visit'-function that appends matched sections...
        self.hf.visit(func)
    
        # ...and return only groups with both /Data and /Info datasets:
        return dataloc.intersection(infoloc)
    
    def _read_datainfo(self, group, prefix=''):
        """Parse a "Data-Info" group into a pd.DataFrame.

        - 'group' a hdf5 group or a string-location to a group
        - 'prefix' names an optional sub-group
        """
        if isinstance(group, str):
            group = self.hf[group]
        data = group[prefix + 'Data']
        info = group[prefix + 'Info']
        if info.ndim > 1:
            labels = info[0,:]
        else:
            labels = info[:]

        if hasattr(labels[0], 'decode'):
            labels = [b.decode('latin1') for b in labels]
    
        # TODO :: wir haben hier diese doesigen Set/Act werte drin, was wollen wir??
        # if keys[0].endswith('[Set]'):
        #     rv = {key[:-5]: (value, unit)
        #           for key, value, unit in zip(keys, values, units)
        #           if key.endswith('[Set]')}
        # else:
        #     rv = {key: (value, unit)
        #           for key, value, unit in zip(keys, values, units)}

        # siehe auch:

        #def datainfo2df(h5group, selection=slice(None)):
        #    """
        #    Split a Data-Info-group into `pd.DataFrame`s for set- and act-values, respectively.
        #
        #    Note, that the column names are inferred from the Info-dataset and that
        #     the columns of act- and set-dataframe need not overlap!
        #
        #    `h5group`   - a HDF5-group containing datasets "Data" and "Info"
        #    `selection` - [slice, optional] load only a part of the TimeCycle-data
        #    """
        #    from collections import namedtuple
        #    _trace = namedtuple('Trace', ['set', 'act'])
        #
        #    names = (info.decode('latin-1') for info in h5group['Info'][0])
        #    units = (info.decode('latin-1') for info in h5group['Info'][1])
        #
        #    df = pd.DataFrame(h5group['Data'][selection], columns=names)
        #
        #    set_cols = [col for col in df.columns if col.endswith('_Set')]
        #    act_cols = [col for col in df.columns if col.endswith('_Act')]
        #
        #    set_values = df[set_cols]
        #    act_values = df[act_cols]
        #
        #    set_values.columns = [col.replace('_Set', '') for col in set_values.columns]
        #    act_values.columns = [col.replace('_Act', '') for col in act_values.columns]
        #
        #    return _trace(set_values, act_values)
    
    
        return pd.DataFrame(data, columns=labels)
    
    def _read_processed_traces(self, kind, index):
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
        data.index = self.read_index(index)
        
        return data

    def _read_original_traces(self, kind, index):
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
    
        return pd.DataFrame(data, columns=labels, index=self.read_index(index))

