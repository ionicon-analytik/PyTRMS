# PyTRMS

This is the official **Ionicon** Python toolbox for proton-transfer reaction mass-spectrometry (PTR-MS).


## Lab automation

Write simple Python scripts to automate your measurement process and get repeatable
results.

For example, perform ten measurements of one minute each and save the datafiles in a
folder. The filename is automatically set to the timestamp at the start of the
measurement.

```python
import pytrms

folder = 'D:/Data/one_minute_each'

for i in range(10):
    measurement = ptr.measure(folder, 'localhost')
    measurement.start()
    measurement.wait(60, 'measuring for one minute...')
    measurement.stop()
```

## Postprocessing and Pandas support

For simple analysis tasks, use the Python package to read and analyse the *hdf5*
files. Traces are available as `Pandas.DataFrame`.

```python
import glob
import pandas as pd
import pytrms

batch = []
for filename in glob.rec('D:/Data/my_experiment/*.h5'):
    batch.append(pytrms.Measurement(filename))

averages = []
for measurement in batch:
    dataframe = measurement.traces
    dataframe.write_csv(measurement.path + '_avg.tsv', sep='\t')
    averages.append(dataframe.avg())

pd.concat(averages).write_csv('grand_average.tsv', sep='\t')
```

## Online analysis in real-time

The `Measurement` can register callback functions that are executed on every
cycle with the current trace data:

```python
import pytrms

m = pytrms.measure('localhost')

def oxygen_watchdog(meas, trace):
    if trace['O2_level'] < 10_000:
        print('oxygen level critical! closing valve 1...')
        meas.set('Valve_1', 0)

def detect_threshold(meas, trace):
    if trace['H2o_level'] > 20_000:
        print('water level above threshold! aborting.')
        meas.stop()

ema = 1
alpha = 0.2
file = 'C:/Temp/m_42_avg.dat'
def moving_average(meas, trace):
    ema = alpha * trace['m_42'] + (1-alpha) * ema
    with open(file, 'a') as f:
        f.write(str(ema) + '\n')
    
m.register_callback(oxygen_watchdog)
m.register_callback(detect_threshold)
m.register_callback(moving_average)

m.start()

```

## Use as a context manager (TODO)

The `Measurement` serves as a context in which the experiment is running:

```python
import pytrms

meas = pytrms.measure(host='localhost')

print(meas)  # prints PrepareMeasurement

with meas as running:
    print(meas)  # prints RunningMeasurement
    meas.wait(3)

print(meas)  # prints FinishedMeasurement
```

## Getting started

Download and install the latest Python version if you have not done so. **Ionicon**
recommends to [download Python 3.9 for Windows](https://www.python.org/ftp/python/3.9.12/python-3.9.12-amd64.exe).
This will install the Python executable along with the package manager *pip*. 
Using *pip* is the preferred way to get the latest version of *PyTRMS*, but other
solutions like *Anaconda* should also work. In a terminal type

```
python -m pip install --upgrade pytrms
```

to install the latest release from *PyPI*. This command can also be used at any later
time to upgrade to the newest version.


### Running the examples

This assumes you have a **Ionicon PTR-MS** connected to your PC and running the 
**ioniTOF** server with the **Ionicon webAPI**. 

Download and extract the examples folder (by clicking on `Code` and selecting
`Download ZIP` from the dropdown menu).
The Python scripts can be run by simply double-clicking them.
If something is not working correctly, the setup may be broken. 
Repeat the steps from the [Getting started](https://github.com/ionicon-analytik/PyTRMS#getting-started)
section and make sure to use the default options.


