from functools import partial

import h5py
import pandas as pd


def print_all(path):
    """Look for data-info traces."""
    provider = h5py.File(path, 'r')

    def func(object_name):
        # defines a 'visit'-function that removes matched sections one by one
        print(object_name)
        return None

    provider.visit(func)


def locate_datainfo(path):
    """Look for data-info traces."""
    provider = h5py.File(path, 'r')

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

    provider.visit(func)

    return dataloc.intersection(infoloc)


def read_datainfo(path, groupname):
    df = h5py.File(path, 'r')

    group = df[groupname]
    data = group['Data']
    info = group['Info']
    names = [b.decode('latin1') for b in info[0,:]]

    return pd.DataFrame(data, columns=names)


def get_addtraces(path):
    frames = []
    for loc in locate_datainfo(path):
        frames.append(read_datainfo(path, loc))

    return pd.concat(frames, axis='columns')


def get_traces(path, kind='raw'):
    df = h5py.File(path, 'r')

    loc = 'TRACEdata/Trace' + kind.capitalize()
    try:
        data = df[loc]
    except KeyError as exc:
        msg = ("Unknown trace-type! `kind` must be one of 'raw', 'corrected' or "
               "'concentration'.")
        raise KeyError(msg) from exc

    info = df['TRACEdata/TraceInfo']
    labels = [b.decode('latin1') for b in info[1,:]]

    return pd.DataFrame(data, columns=labels)

def _labview_to_posix(t):
    return pd.Timestamp(t-2082844800, unit='s')


def get_index(path, kind='abs_cycle'):
    df = h5py.File(path, 'r')

    lut = {
            'REL_CYCLE': (0, lambda a: a.astype('int', copy=False)),
            'ABS_CYCLE': (1, lambda a: a.astype('int', copy=False)),
            'ABS_TIME': (2, lambda a: list(map(_labview_to_posix, a))),
            'REL_TIME': (3, lambda a: list(map(partial(pd.Timedelta, unit='s'), a))),
    }
    info = df['SPECdata/Times']
    try:
        _N, convert = lut[kind.upper()]
    except KeyError as exc:
        msg = "Unknown index-type! `kind` must be one of {0}.".format(', '.join(lut.keys()))
        raise KeyError(msg) from exc

    index = info[:, _N]

    return convert(index)

