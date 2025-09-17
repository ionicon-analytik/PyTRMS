from . import _logging
from .._base import _IoniClientBase

log = _logging.getLogger(__name__)


class IoniDummy(_IoniClientBase):
    '''A mock for any 'IoniClient' (modbus, mqtt, ...) that can be used
    in places where no connection to the instrument is possible or desirable.
    '''

    @property
    def is_connected(self):
        return self.__is_connected

    __is_connected = False

    @property
    def is_running(self):
        return self.__is_running

    __is_running = False

    def connect(self, timeout_s=0):
        log.info(f'pretending to connect to server')
        self.__is_connected = True

    def disconnect(self):
        log.info(f'pretending to disconnect to server')
        self.__is_connected = False

    def start_measurement(self, path=None):
        log.info(f'pretending to start measurement ({path = })')
        self.__is_running = True

    def stop_measurement(self, future_cycle=None):
        log.info(f'pretending to stop measurement ({future_cycle = })')
        self.__is_running = False

    def __init__(self, host='localhost', port=1234):
        super().__init__(host, port)
        self.connect()

