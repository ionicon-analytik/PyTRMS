####################################################
#                                                  #
# example script for post-processing breath files  #
#                                                  #
#                                                  #
####################################################
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
    
        # load a Ionicon .h5 file for post-processing the traces:
        measurement = pytrms.load(file)
        traces = measurement.traces
    
        water_cluster = traces['*(H2O)3H+']
        
        inhale, exhale = breath_tracker(track_signal=water_cluster)
    
        # the inhale/exhale marker can be used as 'boolean indexes' to compute an average
        # of the regions of interest only:
        avg_inhale = traces[inhale].mean()
        avg_exhale = traces[exhale].mean()

        # combine the pd.Series to a pd.DataFrame with two columns...
        avg = pd.concat([avg_inhale, avg_exhale], axis='columns')
        # ...and save as a .tsv file to be imported in excel:
        avg.to_csv(join(dirname(file), base+'.tsv'), sep='\t', header=['inhale', 'exhale'])
    
        # finally, create a plot under the same filename, but with a '.jpg' file extension:
        fig, _ = pytrms.plot_marker(water_cluster, marker=exhale)
        fig.savefig(join(dirname(file), base+'.jpg'))

