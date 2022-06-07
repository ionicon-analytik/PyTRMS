# PyTRMS

This is the official **Ionicon** Python toolbox for proton-transfer reaction mass-spectrometry (PTR-MS). 

Install from `PyPI` (see also [getting started](https://github.com/ionicon-analytik/PyTRMS#getting-started)):
```bash
>> pip install -U pytrms
```

## Postprocessing (with Pandas support)

For simple analysis tasks use the `PyTRMS` Python package to read and analyse Ionicon
*hdf5* files. The [Pandas](https://pandas.pydata.org/pandas-docs/stable/index.html)
Python package is the de-facto standard for data analysis. Use `PyTRMS` to load the
traces directly into a `Pandas.DataFrame`.

In the following example, the traces (i.e. timeseries data) is loaded from a datafile. We are looking for traces containing the term 'H2O' and print out some statistics:

```python
>>> import pytrms
>>> import pandas as pd

>>> measurement = pytrms.load('examples/data/peter_emmes_2022-03-31_08-51-13.h5')
>>> traces = measurement.get_traces('concentration', index='abs_time')
>>> water_columns = [col for col in traces.columns if 'H2O' in col]
>>> for col_name in sorted(water_columns): print(col_name)
*(FeH2O2)H+
*(H2O)+
*(H2O)2H+
*(H2O)2H+ i_17O
*(H2O)2H+ i_18O
*(H2O)3H+
*(H2O)3H+ i_18O
*(H2O)4H+
*(H2O)H+
*(H2O)H+  i_18O
H2O.H3O+ (Cluster)
H2O_Act
H2O_Set

>>> measurement.traces[['*(H2O)+', '*(H2O)H+', '*(H2O)2H+']].describe()
           *(H2O)+     *(H2O)H+    *(H2O)2H+
count   129.000000   129.000000   129.000000
mean    865.904846   980.209534  6049.917480
std     320.313477   826.358704  3256.141846
min     399.933929   170.015930  1947.956299
25%     584.200745   224.781387  2227.153320
50%     822.613037   712.026062  8409.678711
75%    1161.566528  1466.957397  9112.859375
max    1476.455444  2872.100098  9476.558594

```

When analysing a bunch of datafiles, we can leverage the full power of Python to
collect files from a directory tree and use sorting functions to sort our batch e.g.
by the start time:

```python
>>> from glob import iglob
>>> from operator import attrgetter

>>> loader = (pytrms.load(file) for file in iglob('examples/data/*.h5'))
>>> batch = sorted(loader, key=attrgetter('timezero'))
>>> for measurement in batch: print(measurement.filename)
examples/data/peter_emmes_2022-03-31_08-51-13.h5
examples/data/peter_emmes_2022-03-31_08-59-30.h5
examples/data/peter_emmes_2022-03-31_09-10-08.h5
examples/data/peter_emmes_2022-03-31_09-20-31.h5
examples/data/peter_emmes_2022-03-31_09-29-40.h5

```

## Lab automation

When performing many consecutive and repetitive measurements, it is desirable to get
repeatable results. With the `PyTRMS` package, measurements can be easily scripted.

For example, perform ten measurements of one minute each and save the datafiles in a
folder. The filename is automatically set to the timestamp at the start of the
measurement.

```python
>>> import pytrms
>>> from pytrms.testing import connect_ as connect  # (for testing)

# initialize a connection to a PTR instrument server
# (when connecting to an instrument use `pytrms.connect(..)`):
>>> ptr = connect('localhost')  # doctest: +ELLIPSIS
<pytrms.instrument.BusyInstrument object at 0x...>
<pytrms.instrument.IdleInstrument object at 0x...>

>>> ptr  # doctest: +ELLIPSIS
<pytrms.instrument.IdleInstrument object at 0x...>

# the instrument is idle, let's start a measurement:
>>> ptr.start('/tmp/pytrms-test/')  # doctest: +ELLIPSIS
<pytrms.instrument.BusyInstrument object at 0x...>
<pytrms.instrument.RunningInstrument object at 0x...>

>>> ptr.wait(1, 'collecting data for a humble second...')
collecting data for a humble second...

# enough, let's stop the measurement:
>>> ptr.stop()  # doctest: +ELLIPSIS
<pytrms.instrument.BusyInstrument object at 0x...>
<pytrms.instrument.IdleInstrument object at 0x...>

```


## Getting started

Download and install the latest Python version if you have not done so. **Ionicon**
recommends to [download Python 3.8 for Windows](https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe).
This will install the Python executable along with the package manager *pip*. 
Using *pip* is the preferred way to get the latest version of *PyTRMS*, but other
solutions like *Anaconda* should also work. In a terminal type

```
python -m pip install --upgrade pytrms
```

to install the latest release from *PyPI*. This command can also be used at any later
time to upgrade to the newest version.


### Running the examples

Download and extract the examples folder (by clicking on `Code` and selecting
`Download ZIP` from the dropdown menu).
The Python scripts can be run by simply double-clicking them.
If something is not working correctly, the setup may be broken. 
Repeat the steps from the [Getting started](https://github.com/ionicon-analytik/PyTRMS#getting-started)
section and make sure to use the default options.

For testing purposes it is strongly recommended to install the `PyTRMS` package in a fresh
virtual environment, separated from the system-wide installed Python packages.

If you have installed [Python Poetry](https://python-poetry.org/docs/#osx--linux--bashonwindows-install-instructions), 
managing the dependencies is a breeze. In the pytrms folder type `poetry install` to
install the `PyTRMS` package and its dependencies in a fresh virtual environment. To then
use any python command in this virtual environment, simply prefix it with `poetry run`,
for example like this:
`> poetry run python examples\breath_tracking.py`

Without poetry, create and activate a fresh virtual environment, then install the
requirements:
```bash
> python -m venv test-pytrms
> .\test-pytrms\bin\activate
> python -m pip install -r examples\REQUIRES.txt
```

You may now run the examples like this:
```bash
> python examples\breath_tracking.py
```

Note, that the online examples assume that you have a **Ionicon PTR-MS** connected to
your PC and running the which is running a **ioniTOF** server with the **Ionicon webAPI**. 

