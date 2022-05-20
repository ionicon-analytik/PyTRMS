
from .abstract.traceable import Traceable

class H5Source(Traceable):

    @property
    def timezero(self):
        raise NotImplementedError

