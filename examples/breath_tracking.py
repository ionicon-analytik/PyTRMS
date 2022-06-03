from glob import glob
import pytrms
from os.path import basename, splittext, dirname, join

import pandas as pd


def breath_tracker(water_cluster):
    '''
    Mark the time periods of breathing and exhaling.
    '''
    intake = water_cluster < 40_000
    exhale = water_cluster > 70_000

    return intake, exhale


patient = 'peter'
files = glob(f'**/{patient}_*.h5'))


for file in files:
    base, _ = splittext(basename(file))
    print('processing', base, '...')

    measurement = pytrms.load(file)
    traces = measurement.traces

    water_cluster = traces['*(H2O)2H+']
    
    intake, exhale = breath_tracker(water_cluster)

    traces[intake].mean().to_csv(join(dirname(file), base+'_intake.tsv'), sep='\t')
    traces[exhale].mean().to_csv(join(dirname(file), base+'_exhale.tsv'), sep='\t')

    # traces.plot(..., join(dirname(file), base+'.jpg'))

