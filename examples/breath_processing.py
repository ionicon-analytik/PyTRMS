####################################################
#                                                  #
# example script for post-processing breath files  #
#                                                  #
#                                                  #
####################################################
import sys
from glob import glob
from os import path

import pandas as pd
import numpy as np

import pytrms
from pytrms.plotting import plot_marker


def breath_tracker(track_signal, percent_max = 0.4):
    '''
    Mark the time periods of breath inhale and exhale.
    '''
    threshold = percent_max * np.max(track_signal)

    inhale = track_signal < threshold
    exhale = track_signal > threshold

    return inhale, exhale


if __name__ == '__main__':

    args = iter(sys.argv)
    us = next(args)
    patient = next(args, 'peter_emmes')
    data_dir = next(args, '.')

    files = glob(f'{data_dir}/**/{patient}_*.h5', recursive=True)


    for file in files:
        base, _ = path.splitext(path.basename(file))
        print('processing', base, '...')

        # load a Ionicon .h5 file for post-processing the traces:
        measurement = pytrms.load(file)
        traces = measurement.read_traces()

        water_cluster = traces['*(H2O)3H+']

        inhale, exhale = breath_tracker(track_signal=water_cluster)

        # the inhale/exhale marker can be used as 'boolean indexes' to compute an average
        # of the regions of interest only:
        avg_inhale = traces[inhale].mean()
        avg_exhale = traces[exhale].mean()

        # combine the pd.Series to a pd.DataFrame with two columns...
        avg = pd.concat([avg_inhale, avg_exhale], axis='columns')
        # ...and save as a .tsv file to be imported in excel:
        avg.to_csv(path.join(path.dirname(file), base+'.tsv'), sep='\t', header=['inhale', 'exhale'])

        # finally, create a plot under the same filename, but with a '.jpg' file extension:
        fig, _ = plot_marker(water_cluster, marker=exhale)
        fig.savefig(path.join(path.dirname(file), base + '.jpg'))
        print(f'saved JPG to {path.abspath(data_dir)}')