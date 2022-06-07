import sys
from glob import glob
from os.path import basename, splitext, dirname, join

try:
    import pytrms
except ModuleNotFoundError:
    # find module if running from the example folder
    # in a cloned repository from GitHub:
    sys.path.insert(0, join(dirname(__file__), '..'))
    import pytrms

print('using', pytrms.__path__)

import pandas as pd
import numpy as np


def breath_tracker(track_signal, percent_max = 0.4):
    '''
    Mark the time periods of breath inhale and exhale.
    '''
    threshold = percent_max * np.max(track_signal)

    inhale = track_signal < threshold
    exhale = track_signal > threshold

    return inhale, exhale


if __name__ == '__main__':

    patient = 'peter_emmes'
    files = glob(f'**/{patient}_*.h5', recursive=True)
    

    for file in files:
        base, _ = splitext(basename(file))
        print('processing', base, '...')
    
        measurement = pytrms.load(file)
        traces = measurement.traces
    
        water_cluster = traces['*(H2O)3H+']
        
        inhale, exhale = breath_tracker(water_cluster)
    
        avg = pd.concat([traces[inhale].mean(), traces[exhale].mean()], axis='columns')
        avg.to_csv(join(dirname(file), base+'.tsv'), sep='\t', header=['inhale', 'exhale'])
    
        fig, _ = pytrms.plot_marker(water_cluster, marker=exhale)
        fig.savefig(join(dirname(file), base+'.jpg'))

