import os.path
from functools import partial, lru_cache
from itertools import islice

import h5py
import numpy as np
import pandas as pd

from .._base import itype
from ..helpers import convert_labview_to_posix

__all__ = ['IoniTOFReader', 'GroupNotFoundError']


class GroupNotFoundError(KeyError):
    pass


class IoniTOFReader:

    @property
    @lru_cache
    def time_of_meas(self):
        """The pandas.Timestamp of the 0th measurement cycle."""
        return next(self.iter_index('abs_time')) - next(self.iter_index('rel_time'))

    @property
    @lru_cache
    def time_of_file(self):
        """The pandas.Timestamp of the 0th file cycle."""
        # ..which is *not* the 1st file-cycle, but the (unrecorded) one before..
        file0 = next(self.iter_index('abs_time')) - pd.Timedelta(self.single_spec_duration_ms, 'ms')
        # ..and should never pre-pone the measurement time:
        return max(file0, self.time_of_meas)

    @property
    @lru_cache
    def time_of_file_creation(self):
        """The pandas.Timestamp of the file creation."""
        return convert_labview_to_posix(float(self.hf.attrs['FileCreatedTime_UTC']), self.utc_offset_sec)

    @property
    @lru_cache
    def utc_offset_sec(self):
        """The pandas.Timestamp of the 0th file cycle."""
        return int(self.hf.attrs['UTC_Offset'])

    @property
    def inst_type(self):
        return str(self.hf.attrs.get('InstrumentType', [b'',])[0].decode('latin-1'))

    @property
    def sub_type(self):
        return str(self.hf.attrs.get('InstSubType', [b'',])[0].decode('latin-1'))

    @property
    def serial_nr(self):
        return str(self.hf.attrs.get('InstSerial#', [b'???',])[0].decode('latin-1'))

    @serial_nr.setter
    def serial_nr(self, number):
        path = self.filename
        self.hf.close()
        try:
            hf = h5py.File(path, 'r+')
            hf.attrs['InstSerial#'] = np.array([str(number).encode('latin-1')], dtype='S')
            hf.flush()
            hf.close()
        except OSError:
            # well it didn't work..
            pass
        finally:
            self.hf = h5py.File(path, 'r', swmr=False)

    @property
    def number_of_timebins(self):
        return int(self.hf['SPECdata/Intensities'].shape[1])

    @property
    def timebin_width_ps(self):
        return float(self.hf.attrs.get('Timebin width (ps)'))

    @property
    def poisson_deadtime_ns(self):
        return float(self.hf.attrs.get('PoissonDeadTime (ns)'))

    @property
    def pulsing_period_ns(self):
        return float(self.hf.attrs.get('Pulsing Period (ns)'))

    @property
    def start_delay_ns(self):
        return float(self.hf.attrs.get('Start Delay (ns)'))

    @property
    def single_spec_duration_ms(self):
        return float(self.hf.attrs.get('Single Spec Duration (ms)'))

    def __init__(self, path):
        self.hf = h5py.File(path, 'r', swmr=False)
        self.filename = os.path.abspath(self.hf.filename)

    table_locs = {
        'primary_ions': '/PTR-PrimaryIons',
        'transmission': '/PTR-Transmission',
    }

    def get_table(self, table_name):
        try:
            grp = self.hf.get(IoniTOFReader.table_locs[table_name])
            assert grp is not None, "missing dataset in hdf5 file"
        except KeyError as exc:
            raise KeyError(str(exc) + f", possible values: {list(IoniTOFReader.table_locs.keys())}")

        rv = []
        for i, name in enumerate(s.decode('latin-1') for s in grp['Descriptions']):
            # Note: the dataset is 10 x 2 x 10 by default, but we remove all empty rows...
            if not len(name):
                continue

            dset = grp['Masses_Factors'][i]
            # ...and columns:
            filled = np.all(dset, axis=0)
            masses = dset[0, filled]
            values = dset[1, filled]
            rv.append(itype.table_setting_t(name, list(zip(masses, values))))

        return rv

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
        rv.index = list(self.iter_index(index))

        # de-duplicate trace-columns to prevent issues...
        return rv.loc[:, ~rv.columns.duplicated()]

    def read_calctraces(self, index='abs_cycle'):
        """Reads the calculated traces into a DataFrame.

        - 'index' one of abs_cycle|abs_time|rel_cycle|rel_time
        """
        return self.read_addtraces('CalcTraces', index)

    @lru_cache
    def read_traces(self, kind='conc', index='abs_cycle', force_original=False):
        """Reads the peak-traces of the given 'kind' into a DataFrame.

        If the traces have been post-processed in the Ionicon Viewer,
        those will be used, unless `force_original=True`.

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

    def read_all(self, kind='conc', index='abs_cycle', force_original=False):
        """Reads all traces into a DataFrame.

        If the traces have been post-processed in the Ionicon Viewer,
        those will be used, unless `force_original=True`.

        - 'kind' one of raw|corr|conc
        - 'index' one of abs_cycle|abs_time|rel_cycle|rel_time
        - 'force_original' ignore the post-processed data
        """
        # ...and throw it all together:
        return pd.concat([
            self.read_traces(kind, index, force_original),
            self.read_addtraces(None, index),
        ], axis='columns')

    def iter_index(self, kind='abs_cycle'):
        lut = {
                'rel_cycle': (0, lambda a: iter(a.astype('int', copy=False))),
                'abs_cycle': (1, lambda a: iter(a.astype('int', copy=False))),
                'abs_time':  (2, lambda a: map(partial(convert_labview_to_posix, utc_offset_sec=self.utc_offset_sec), a)),
                'rel_time':  (3, lambda a: map(partial(pd.Timedelta, unit='s'), a)),
        }
        try:
            _N, convert2iterator = lut[kind.lower()]
        except KeyError as exc:
            msg = "Unknown index-type! `kind` must be one of {0}.".format(', '.join(lut.keys()))
            raise KeyError(msg) from exc
    
        return convert2iterator(self.hf['SPECdata/Times'][:, _N])

    @lru_cache
    def make_index(self, kind='abs_cycle'):
        return pd.Index(self.iter_index(kind))
    
    def __len__(self):
        return self.hf['SPECdata/Intensities'].shape[0]

    def iter_specdata(self, start=None, stop=None):
        has_mc_segments = False # self.hf.get('MassCal') is not None

        add_data_dicts = {ad_info.split('/')[1]: self.read_addtraces(ad_info)
            for ad_info in self._locate_datainfo()
            if ad_info.startswith('AddTraces')}

        for i in islice(range(len(self)), start, stop):
            tc = itype.timecycle_t(*self.hf['SPECdata/Times'][i])
            iy = self.hf['SPECdata/Intensities'][i]
            if has_mc_segments:
                raise NotImplementedError("new style mass-cal")
            else:
                mc_map = self.hf['CALdata/Mapping']
                mc_pars = self.hf['CALdata/Spectrum'][i]
                mc_segs = mc_pars.reshape((1, mc_pars.size))
                mc = itype.masscal_t(0, mc_map[:, 0], mc_map[:, 1], mc_pars, mc_segs)
            ad = dict()
            for ad_info, ad_frame in add_data_dicts.items():
                ad_series = ad_frame.iloc[i]
                unit = ''
                view = 1
                ad[ad_info] = [itype.add_data_item_t(val, name, unit, view)
                    for name, val in ad_series.items()]
            yield itype.fullcycle_t(tc, iy, mc, ad)

    def list_file_structure(self):
        """Lists all hdf5 group- and dataset-names."""
        # this walks all h5 objects in alphabetic order:
        obj_names = set()
        self.hf.visit(lambda obj_name: obj_names.add(obj_name))

        return sorted(obj_names)
    
    def list_addtrace_groups(self):
        """Lists the recorded additional trace-groups."""
        return sorted(self._locate_datainfo())
    
    def __repr__(self):
        return "<%s (%s) [no. %s] %s>" % (self.__class__.__name__,
                self.inst_type, self.serial_nr, self.hf.filename)

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
    
    def traces(self):
        """Returns a  'pandas.DataFrame' with all traces concatenated."""
        return self.read_all(kind='conc', index='abs_cycle', force_original=False)

    # TODO :: optimize: gib eine 'smarte' Series zurueck, die sich die aufgerufenen
    # columns merkt! diese haelt die ganze erste Zeile des datensatzes. 
    # ab dem zweiten durchgang kann die Series auf diese columns
    # reduziert werden
    # uuuuuuuuuund so geht's:
    # - defaultdict ~> factory checkt parIDs! ~> sonst KeyError
    #   |__ wird dann bei bedarf ge-populated
    # 
    # das sourcefile / measurement soll sich wie ein pd.DataFrame "anfuehlen":
        
    # das loest das Problem, aus einer "Matrix2 gezielt eine Zeile oder eine "Spalte" 
    #  oder alles (d.h. iterieren ueber Zeilen) zu selektieren und zwar intuitiv!!

    # IDEE: die .traces "tun so, als waren sie ein DataFrame"
    #  (keine inheritance, nur ein paar methoden werden durch effizientere ersetzt):
    # wir brauchen:
    # 1. _len_getter ~> reace condi vermeiden!
    # 2. |__ index_getter
    # 3. _column_getter
    # 4. _row_getter
    # 5. parID_resolver ~> keys() aus ParID.txt zu addtrace-group + column!
    
    ###################################################################################
    #                                                                                 #
    # ENDZIEL: times u. Automation fuer die "letzte" Zeile an die Datenbank schicken! #
    #                                                                                 #
    ###################################################################################

    def __getitem__(self, key):
        index = self.make_index()
        if isinstance(key, str):
            return pd.Series(self._get_datacolumn(key), name=key, index=index)
        else:
            return pd.DataFrame({k: self._get_datacolumn(k) for k in key}, index=index)

    @lru_cache
    def _build_datainfo(self):
        """Parse all "Data-Info" groups and build a lookup-table.
        """
        lut = dict()
        for group_name in self._locate_datainfo():
            info = self.hf[group_name + '/Info']
            for column, label in enumerate(info[:] if info.ndim == 1 else info[0,:]):
                if hasattr(label, 'decode'):
                    label = label.decode('latin1')
                lut[label] = group_name + '/Data', column

        return lut

    def _get_datacolumn(self, key):
        lut = self._build_datainfo()
        if key not in lut and not key.endswith('_Act') and not key.endswith('_Set'):
            # fallback to act-value (which is typically wanted):
            key = key + '_Act'

        dset_name, column = lut[key]  # may raise KeyError

        return self.hf[dset_name][:,column]
    
    def loc(self, label):
        if isinstance(label, int):
            return self.iloc[self.make_index('abs_cycle')[label]]
        else:
            return self.iloc[self.make_index('abs_time')[label]]

    def iloc(self, offset):
        # build a row of all trace-data...
        lut = self._build_datainfo()
        name = self.make_index()[offset]
        data = {key: self.hf[h5_loc][offset,col] for key, [h5_loc, col] in lut.items()}

        return pd.Series(data, name=name)

    @lru_cache
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
        data.index = list(self.iter_index(index))
        
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
    
        return pd.DataFrame(data, columns=labels, index=list(self.iter_index(index)))

