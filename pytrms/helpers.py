import requests.exceptions
import pandas as pd

__all__ = ['convert_labview_to_posix', 'PTRConnectionError']


def convert_labview_to_posix(ts):
    '''Create a `Pandas.Timestamp` from LabView time.'''
    posix_time = ts - 2082844800

    return pd.Timestamp(posix_time, unit='s')


class PTRConnectionError(requests.exceptions.ConnectionError):
    pass


