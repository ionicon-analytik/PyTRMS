#################################################
#                                               #
# Ionicon WebAPI - Python client                #
#                                               #
# this module requires the 'requests' package   #
#                                               #
# >> pip install --user requests                #
#                                               #
#################################################
import os
import time

import requests


class IoniClient:
    '''
    Access the Ionicon WebAPI.

    Usage:
    >>> client = IoniClient()
    >>> client.get('TPS_Pull_H')
    {'TPS_Pull_H': 123.45, ... }

    >>> client.set('TPS_Pull_H', 42)
    {'TPS_Pull_H': 42.0, ... }

    >>> client.start_measurement()
    ACK

    >>> client.host, client.port
    ('localhost', 8002)
    
    '''
    def __init__(self, host='localhost', port=8002):
        self.host = host
        self.port = port
        self.measuring = False  # TODO :: measuring status abfragen (property)!

    @property
    def baseurl(self):
        return f'http://{self.host}:{self.port}/Ic_WebAPI'

    def get(self, varname):
        uri = self.baseurl + '/WebAPI_Get'
        payload = {varname: '?'}
        r = requests.get(uri, params=payload)

        return r.text

    def get_traces(self):
        uri = self.baseurl + '/TRACES_WebAPI_Get' + '?'
        r = requests.get(uri)

        return r.text

    def set(self, varname, value):
        uri = self.baseurl + '/WebAPI_Set'
        payload = {varname: value}
        r = requests.post(uri, data=payload)

        return r.text

    def set_filename(self, filename):
        return self.set('ACQ_SRV_SetFullStorageFile', os.path.normpath(filename))

    def start_measurement(self, filename=''):
        self.measuring = True  # TODO :: measuring status abfragen!
        if filename:
            return self.set('ACQ_SRV_Start_Meas_Auto', os.path.normpath(filename))

        return self.set('ACQ_SRV_Start_Meas_Quick', 1)

    def stop_measurement(self):
        self.measuring = False  # TODO :: measuring status abfragen!
        return self.set('ACQ_SRV_Stop_Meas', 1)


if __name__ == '__main__':
    import sys
    client = IoniClient()

    if len(sys.argv) == 2:
        print(client.get(sys.argv[1]))
    elif len(sys.argv) == 3:
        print(client.set(sys.argv[1], sys.argv[2]))
    else:
        print(f"""\
                usage:
                  python {sys.argv[0]} <varname> [<value>]
              """)

