import os
import time

#from .abstract.traceable import Traceable


class Measurement:
    '''
    Base class for PTRMS measurements or batch processing.

    Subclasses of `Process` must implement the `__iter__()` function to guarantee
    the common behaviour for online and offline processing with one or multiple
    datafiles.
    '''
    time_format = "%Y-%m-%d_%H-%M-%S"

    @staticmethod
    def _name_convention(fmt, prefix):
        '''Factory for the next filename.'''
        return prefix + '_' + time.strftime(fmt, time.localtime())

    def _make_filename(self):
        basename = self.basename if self.basename else self._name_convention(self.time_format, self.prefix)
        basename += '.h5'

        return os.path.join(self.home, basename)

    @property
    def is_running(self):
        if client is None:
            return False

        return True  # TODO :: status abfragen!! (Kandidat: )
        self.client.get('ACQ_SRV_CurrentState')

    def __init__(self, path, client=None, prefix=''):
        if not len(path):
            path = os.getcwd()
        self.home = os.path.abspath(os.path.dirname(path))
        os.makedirs(self.home, exist_ok=True)
        basename = os.path.basename(path)  # may be empty
        self.basename, _ = os.path.splitext(basename)
        self.client = client
        self.prefix = prefix
        self.datafiles = []
        self.settings = {}
#         self._previous_settings = {}  # TODO : memorize old context
#   ODER: gleich einfach mal alles vom server holen..??

    def start():
        if client is None:
            raise Exception('no connection to instrument')

        if len(self.settings):
            self.client.set_many(self.settings)
            print('applied settings')
        filename = self._make_filename()
        if os.path.exists(filename):
            raise Exception(f'{filename} exists and cannot be overwritten')

        self.client.start_measurement(filename)
        self.datafiles.append(filename)
        print(f'started measurement at {time.localtime()}')

    def wait(seconds, reason=''):
        if reason:
            print(reason)
        time.sleep(seconds)

    def stop():
        if client is None:
            raise Exception('no connection to instrument')

        self.client.stop_measurement()
        print(f'stopped measurement at {time.localtime()}')

    def set(varname, value):
        self.client.set(varname, value)
        self.settings.update({varname: value})

    def add_file(path):
        pass
#         self.sources = sorted(self.sources + [H5Source(path)], key=attrgetter('timezero'))


    def find(self, needle):
        self.client.get_traces()

    def iterrows(self):
        return PollingIterator(self.client)


class PollingIterator:  # TODO :: in etwa so, nur anders

    def __init__(self, client):
        self.client = client

    def __iter__(self):
        return self

    def __next__(self):
        if not False: #self.client.measuring:
            raise StopIteration

        time.sleep(1)
        return self.client

