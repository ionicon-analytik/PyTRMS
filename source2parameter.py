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
import re
from collections import namedtuple

import numpy as np
import pandas as pd
import h5py

print(h5py.version.info)

########


from io_utils import datainfo2df

##########

from decorators import *

##########

def parse_source_string(source):
    """
    Extract a source-dictionary from a formatted source string.

    >>> parse_source_string(r"hdf://D:\AME_Data\_2023_06_05__15_34_55.h5:9700:")
    {'path': D:\AME_Data\_2023_06_05__15_34_55.h5, 'begin': 9700, 'end': -1}
    """
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

##########

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
    
        set_all.append(pd.concat([set_ptr, set_tps], axis='columns'))
        act_all.append(pd.concat([act_ptr, act_tps], axis='columns'))

        print(set(set_ptr.index)) # ^ set(set_tps.columns))

    set_df = pd.concat(set_all, axis='index')
    act_df = pd.concat(act_all, axis='index')

    return set_df, act_df

#######

@eventinit
def initialize(db_api):
    j = db_api.get('/api/parameters')

    parname2id = dict()
    for par in j["_embedded"]["parameters"]:
        pid = par["parameterID"] 
        name = par["name"]
        pname = par["prettyName"]
        parname2id[name] = pid
        if pname is not None and pname not in parname2id:
            # don't overwrite DPS_Udrift with PTR_DCS_Udrift O_o
            parname2id[pname] = pid
            # TODO ...ist aber letztlich UNMOEGLICH zuzuordnen, muss man warten

    for name in sorted(parname2id):
        print(name, '~>', parname2id[name])

    return parname2id


@eventhook('average')
def run_the_thing(db_api, avg, parname2id):

    avg_link = avg["_links"]["self"]["href"]

    j = db_api.get(avg_link + '/sources')
    sources = j["_embedded"]["sources"]

    set_df, act_df = collect(sources)

    # negotiate common parameter names...
    
    common_names = list(set(set_df.columns) & parname2id.keys())
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

    endpoint = avg_link + '/parameter_traces'
    db_api.post(endpoint, payload)


