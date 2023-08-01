# in the event of a 'new average':
# 
# get this "source"...
#
# /api/average/xy/source
# {
#   "count": 2,
#   "_embedded": {
#     "sources": [
#       {
#         "path": "D:\\AMEData\\__2023_06_06__19_26_35\\AME_Data___2023_06_06__19_26_35.h5",
#         "begin": 320,
#         "end": 321
#       },
#       {
#         "path": "D:\\AMEData\\__2023_06_06__19_31_56_Action4\\AME_Data___2023_06_06__19_31_56.h5",
#         "begin": 1,
#         "end": 23
#       }
#     ]
#   },
#   "_links": {
# 
#     }
#   }
# }
# 
# ...open the .h5-file(s) 'mr'-mode and
#
# 1) negotiate the ParameterIDs
# 2) upload the average, mean, et.c.
#
# then, wait for the next event until event 'measurement stopped' occurs.
# 
# ALTERNATIVE: CLI-mode (the source is passed as a command-line argument):
#
# >> py source2par.py -s "hdf://D:/foo/bar.h5:320:321" -s "hdf://D:/foo/zoom.h5:1:23"
from collections import namedtuple

import numpy as np
import pandas as pd
import h5py

from pytrms.clients.db_api import IoniConnect
from pytrms.clients.ssevent import SSEventListener

from pytrms.clients import ionitof_url
from pytrms.clients import database_url


print(h5py.version.info)

########

#sources = [
#        r"hdf://D:\Temp\__2023_06_05__15_34_55\AME_Data___2023_06_05__15_34_55_MaxCycle_003.h5:9700:"
#]
#
#current_avg_endpoint = '/api/averages/11'

########

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
    

def parse_source_string(source):
    try:
        scheme, *path, begin, end = source.split(':')
        if scheme != 'hdf':
            raise Exception("unknown scheme: " + scheme)

        return {
            'path': ':'.join(path).lstrip('//'),
            'begin': int(begin) if begin else None,
            'end': int(end) if end else None,
        }
    except ValueError as exc:
        raise Exception("parsing error while parsing source string") from exc


def collect(sources):
    # collect parameters from sources...
    
    set_all = []
    act_all = []
    
    for source in sources:
    
        # Note: yes, we are not collecting identical source-files and
        #  yes, this is inefficient, but the use-case must first arise.
    
        if not isinstance(source, dict):
            source = parse_source_string(source)
    
        source['selection'] = slice(source['begin'], source['end'])
    
        print(source)
    
        hf = h5py.File(source['path'], mode='r', swmr=True)
    
        set_ptr, act_ptr = datainfo2df(hf['/AddTraces/PTR-Instrument'], source['selection'])
        set_tps, act_tps = datainfo2df(hf['/AddTraces/TOFSupply'], source['selection'])
    
        set_all += [set_ptr, set_tps]
        act_all += [act_ptr, act_tps]

    set_df = pd.concat(set_all)
    act_df = pd.concat(act_all)

    return set_df, act_df


def run_the_thing(db_api, sources, current_avg_endpoint):

    set_df, act_df = collect(sources)

    # negotiate common parameter names...
    
    j = db_api.get('/api/parameters')
    parname2id = {par["name"]: par["parameterID"] for par in j["_embedded"]["parameters"]}
    
    common_names = list(set(set_df.columns) & parname2id.keys())<F5>
    set_df = set_df[common_names]
    
    common_names = list(set(act_df.columns) & parname2id.keys())
    act_df = act_df[common_names]
    
    
    # compute averages and construct payload...
    
    upload = pd.DataFrame([set_df.mean(), act_df.mean(), act_df.min(), act_df.max()]).T
    upload.columns = ["setValue", "actMean", "actMin", "actMax"]
    upload["parameterID"] = [parname2id[parname] for parname in upload.index]
    
    print(upload)
    
    payload = {
        "quantities": [
            item._asdict() for item in upload.itertuples()
        ]
    }

    endpoint = current_avg_endpoint + '/parameter_traces'
    db_api.put(endpoint, payload)



## TODO :: captain hook !
#
#    hier kommt ein "executor" hin!
#
#     lade hook-funktionen aus Python module
#     ..markiert mit gewuenschtem event
#     ..und die werden dann ausgefuerht
#     ..ganz genau wie die AME plugins (nur in Python)
#    => das ist dann die Blaupause fuer die AME-execution!
#
#   und man kann alle moeglichen hook-skripte in einen Ordner schmeissen und draus laden..
#   ..oder dann eben gesammelt auf eine ganze reihe von averages ausfuehren!
#
#  so stell ich mir das vor.
##

def main(args):

    if len(args) > 1:
        database_url = str(args[1])

    db_api = IoniConnect(database_url)
    sse = SSEventListener(database_url + '/api/events')
    
    print("listening to average events...")
    sse.subscribe('new average')

    for event in sse:
        current_avg_endpoint = event

        print('got:', current_avg_endpoint)

        j = db_api.get(current_avg_endpoint + '/sources')

        sources = j["_embedded"]["sources"]

        run_the_thing(db_api, sources, current_avg_endpoint)



if __name__ == '__main__':
    import sys
    main(sys.args)

