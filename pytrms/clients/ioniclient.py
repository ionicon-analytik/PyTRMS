#################################################
#                                               #
# Ionicon WebAPI - Python client                #
#                                               #
# this module requires the 'requests' package   #
#                                               #
# >> pip install --user requests                #
#                                               #
#################################################
import ntpath
import time

import requests


class IoniClient:
    '''
    Access the Ionicon WebAPI.

    Usage:
    > client = IoniClient()
    > client.get('TPS_Pull_H')
    {'TPS_Pull_H': 123.45, ... }

    > client.set('TPS_Pull_H', 42)
    {'TPS_Pull_H': 42.0, ... }

    > client.start_measurement()
    ACK

    > client.host, client.port
    ('localhost', 8002)
    
    '''
    def __init__(self, host='localhost', port=8002):
        self.host = host
        self.port = port

    @property
    def baseurl(self):
        return f'http://{self.host}:{self.port}/Ic_WebAPI'

    def get(self, varname):
        uri = self.baseurl + '/WebAPI_Get'
        payload = {varname: '?'}
        r = requests.get(uri, params=payload, timeout=10)

        return r.text

    def get_many(self, varnames):
        uri = self.baseurl + '/WebAPI_Get'
        payload = {varname: '?' for varname in varnames}
        r = requests.get(uri, params=payload, timeout=10)

        return r.text

    def get_traces(self):
        uri = self.baseurl + '/TRACES_WebAPI_Get' + '?'
        r = requests.get(uri, timeout=10)

        return r.text

    def set(self, varname, value):
        uri = self.baseurl + '/WebAPI_Set'
        payload = {varname: value}
        r = requests.post(uri, data=payload, timeout=10)

        return r.text

    def set_many(self, key_value_pairs):
        uri = self.baseurl + '/WebAPI_Set'
        payload = dict(key_value_pairs)
        r = requests.post(uri, data=payload, timeout=10)

        return r.text

    def set_filename(self, filename):
        return self.set('ACQ_SRV_SetFullStorageFile', ntpath.normpath(filename))

    def start_measurement(self, filename=''):
        if filename:
            return self.set('ACQ_SRV_Start_Meas_Auto', ntpath.normpath(filename))

        return self.set('ACQ_SRV_Start_Meas_Quick', 1)

    def stop_measurement(self):
        return self.set('ACQ_SRV_Stop_Meas', 1)
