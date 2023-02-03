# building

## additional includes

Modify the 'np_get_include.props' either in a text-editor or via the 
Visual Studio *property pages*. The correct numpy include directory
is found by executing the following python-command in your virtual 
environment:

```
$ python -c "from numpy.lib.utils import get_include; print(get_include())"
```

## debugging

Both the `Debug` as well as the `Release` configuration should enable
you to attach a debugger to the running instance of *python.exe*. There
may be more than one python process running when python is launched in 
a virtual environment. The correct process is the global one, e.g. the
one installed in `C:/Program Files/Python38`. This can be checked using
the *Process Explorer* from the Windows sysinternals.

The `Py_Debug` configuration needs the python debug-binaries installed
and should not be used and not be necessary.

