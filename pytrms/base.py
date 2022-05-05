import os
import time


class BaseProcess:
    '''
    Base class for PTRMS measurements or batch processing.

    Subclasses of `Process` must implement the `__iter__()` function to guarantee
    the common behaviour for online and offline processing with one or multiple
    datafiles.
    '''
    filename_format = "Cal_%Y-%m-%d_%H-%M-%S"

    @staticmethod
    def _name_convention(fmt, filecount):
        '''Factory for the current filename.

        Gets the `filename_format` string and the current `filecount` as parameters.
        '''
        return time.strftime(fmt, time.localtime())

    def __init__(self, path):
        '''Get a file path or directory.
        '''
        if not len(path):
            path = os.getcwd()
        self._dir = os.path.abspath(os.path.dirname(path))
        self._filename = os.path.basename(path)  # may be empty
        self._filecount = 0
        self._dfiles = []
        os.makedirs(self._dir, exist_ok=True)

    @property
    def filename(self):
        basename = self._name_convention(self.filename_format, self._filecount)
        basename += '.h5'
        return os.path.join(self._dir, basename)

    def __iter__(self):
        raise NotImplementedError

