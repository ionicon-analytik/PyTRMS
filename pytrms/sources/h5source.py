
from .datasource import DataSource

class H5Source(DataSource):

    @property
    def timezero(self):
        raise NotImplementedError

