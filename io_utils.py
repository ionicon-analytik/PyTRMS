from collections import namedtuple

import pandas as pd


_trace = namedtuple('Trace', ['set', 'act'])

def datainfo2df(h5group, selection=slice(None)):
    """
    Split a Data-Info-group into `pd.DataFrame`s for set- and act-values, respectively.

    Note, that the column names are inferred from the Info-dataset and that
     the columns of act- and set-dataframe need not overlap!

    `h5group`   - a HDF5-group containing datasets "Data" and "Info"
    `selection` - [slice, optional] load only a part of the TimeCycle-data
    """
    names = (info.decode('latin-1') for info in h5group['Info'][0])
    units = (info.decode('latin-1') for info in h5group['Info'][1])

    df = pd.DataFrame(h5group['Data'][selection], columns=names)

    set_cols = [col for col in df.columns if col.endswith('_Set')]
    act_cols = [col for col in df.columns if col.endswith('_Act')]

    set_values = df[set_cols]
    act_values = df[act_cols]

    set_values.columns = [col.replace('_Set', '') for col in set_values.columns]
    act_values.columns = [col.replace('_Act', '') for col in act_values.columns]

    return _trace(set_values, act_values)
    
