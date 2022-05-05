# PyTRMS

This is the official **Ionicon** Python toolbox for proton-transfer reaction mass-spectrometry (PTR-MS).


## Lab automation

Write simple Python scripts to automate your measurement process and get repeatable
results!

For example, to perform ten measurements of one minute each and count up the
filename:
```python
import pytrms

ptr = pytrms.webclient()

measurement = ptr.Measure(r'D:\Data\one_minute_each')

for i in range(10):
    measurement.repeat_for(60)
```

## Postprocessing

For simple analysis tasks, use the Python package to read and analyse the *hdf5*
files:

```python
import pytrms

batch = pytrms.h5client(r'D:\Data\my_experiment')
```

## Getting started

Download and install the latest Python version if you have not done so. **Ionicon**
recommends to [download Python 3.9 for Windows](https://www.python.org/ftp/python/3.9.12/python-3.9.12-amd64.exe)
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
Repeat the steps from the `Getting started` section and stick to the defaults.

