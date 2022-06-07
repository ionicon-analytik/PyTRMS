import sys
from glob import glob
from os.path import basename, splitext, dirname, join

try:
    import pytrms
except ModuleNotFoundError:
    # find module if running in cloned folder from GitHub:
    sys.path.insert(0, join(dirname(__file__), '..'))
    import pytrms

print('using', pytrms.__path__)

import pandas as pd
import numpy as np


def breath_tracker_simple(track_signal):
    '''
    Mark the time periods of breath intake and exhale.
    '''
    inhale = track_signal < 40_000
    exhale = track_signal > 70_000

    return inhale, exhale


def breath_tracker_sophisticated(track_signal, cycle_time=1,
        percent_max = 0.9,          # Everything above 90% is considered exhale
        percent_min = 0.05,         # Everything below 5% above background is considered inhale
        percent_increase = 0.2,     # 20% Increase/s is considered too much Variation
        percent_decrease = 0.2      # 20% Decrease/s is considered too much Variation
    ):
    '''
    find the sections of inhale and exhale in `track_signal`.

    this computes a robust minimum and maximum of the signal and uses `percent_min` and
    `percent_max` as thresholds for breath inhale (signal is low) and exhale (signal is
    high), respectively.

    the sections of high signal increase and decrease are left out.

    returns a tuple of two boolean arrays where inhale and exhale was detected.
    '''
    
    # assuming a single breath that can be evaluated takes at least 3 seconds,
    # calculate the number of Cycles that fit within an exhalation (at least 3)
    AVG = max(3 // cycle_time, 3)
    
    # Determine the average of the AVG highest Signals, this eliminates outliers
    sorted_signal = sorted(track_signal)
    max_signal = np.median(sorted_signal[AVG:])
    min_signal = np.median(sorted_signal[:AVG])
    
    signal_increase = np.diff(track_signal) / cycle_time
    signal_increase = np.concatenate((signal_increase[0:1], signal_increase))  # (np.diff shortens the array by one!)

    signal_increase_ascending = np.sort(signal_increase)
    max_signal_increase = np.mean(signal_increase_ascending[AVG//2:])  # use half the points for averaging, exhale and inhale
    max_signal_decrease = np.mean(signal_increase_ascending[:AVG//2])  # use half the points for averaging, exhale and inhale
    
    increasing  = signal_increase > percent_increase*max(max_signal_increase)
    decreasing  = signal_increase < percent_decrease*min(max_signal_decrease)
    
    inhaled = track_signal < min_signal + percent_min * (max_signal - min_signal)
    exhaled = track_signal > percent_max * max_signal

    # exclude cycles (from exhale and inhale) with strong variation upwards or downwards
    inhaled = inhaled & ~increasing & ~decreasing
    exhaled = exhaled & ~increasing & ~decreasing
    
    return inhaled, exhaled
    


patient = 'peter'
files = glob(f'**/{patient}_*.h5', recursive=True)


for file in files:
    base, _ = splitext(basename(file))
    print('processing', base, '...')

    measurement = pytrms.load(file)
    traces = measurement.traces

    water_cluster = traces['*(H2O)2H+']
    
    intake, exhale = breath_tracker_simple(water_cluster)

    traces[intake].mean().to_csv(join(dirname(file), base+'_intake.tsv'), sep='\t')
    traces[exhale].mean().to_csv(join(dirname(file), base+'_exhale.tsv'), sep='\t')

    # traces.plot(..., join(dirname(file), base+'.jpg'))

