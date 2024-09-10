import os
import json
from contextlib import contextmanager

import requests

from . import _logging
from . import database_url, enable_extended_logging

log = _logging.getLogger(__name__)

# TODO :: sowas waer auch ganz cool: die DBAPI bietes sich geradezu an,
#  da mehr object-oriented zu arbeiten:

#   currentVariable = get_component(currentComponentNameAction, ds)
#   currentVariable.save_value({'value': currentValue})

class IoniConnect:

    def __init__(self, url='', session=None):
        if not url:
            url = database_url

        if session is None:
            session = requests.sessions.Session()

        self.url = url
        self.session = session
        self.current_avg_endpoint = None
        self.comp_dict = dict()

    def get(self, endpoint, **kwargs):
        return self._get_object(endpoint, **kwargs).json()

    def post(self, endpoint, data, **kwargs):
        return self._create_object(endpoint, data, 'post', **kwargs).headers.get('Location')

    def put(self, endpoint, data, **kwargs):
        return self._create_object(endpoint, data, 'put', **kwargs).headers.get('Location')

    def _get_object(self, endpoint, **kwargs):
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        if 'headers' not in kwargs:
            kwargs['headers'] = {'content-type': 'application/hal+json'}
        elif 'content-type' not in (k.lower() for k in kwargs['headers']):
            kwargs['headers'].update({'content-type': 'application/hal+json'})
        r = self.session.request('get', self.url + endpoint, **kwargs)
        r.raise_for_status()
        
        return r

    def _create_object(self, endpoint, data, method='post', **kwargs):
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        if not isinstance(data, str):
            data = json.dumps(data)
        if 'headers' not in kwargs:
            kwargs['headers'] = {'content-type': 'application/hal+json'}
        elif 'content-type' not in (k.lower() for k in kwargs['headers']):
            kwargs['headers'].update({'content-type': 'application/hal+json'})
        r = self.session.request(method, self.url + endpoint, data=data, **kwargs)
        if not r.ok:
            log.error(f"POST {endpoint}\n{data}\n\nreturned [{r.status_code}]: {r.content}")
            r.raise_for_status()

        return r

    def iter_events(self):
        """Follow the server-sent-events (SSE) on the DB-API."""
        r = self.session.request('GET', self.url + "/api/events",
                headers={'accept': 'text/event-stream'}, stream=True)
        r.raise_for_status()
        kv_pair = dict()
        for line in r.iter_lines():
            # empty newlines serve as keep-alive and end-of-entry:
            if not line:
                if kv_pair:
                    yield kv_pair
                    kv_pair = dict()
                else:
                    log.debug("sse: still kept alive...")
                continue

            key, val = line.decode().split(':')
            kv_pair[key] = val.strip()

    def refresh_comp_dict(self):
        j = self.get('/api/components')
        self.comp_dict = {component["shortName"]: component
            for component in j["_embedded"]["components"]}
    
    def get_component(self, short_name):
        if not len(self.comp_dict):
            self.refresh_comp_dict()
    
        return self.comp_dict[short_name]

    def create_component(self, short_name):
        payload = {
            "shortName": short_name
        }
        self.post('/api/components', payload)
        self.refresh_comp_dict()

    def create_average(self, endpoint, run, step, action=0, use_mean=True):

        params = {'run': int(run), 'step': int(step), 'usemean': bool(use_mean)}
        if (action != 0):
            params['action'] = int(action)

        timecycles = self.get(endpoint, params)
        self.current_avg_endpoint = self.post('/api/averages', timecycles)

    def save_component_values(self, new_values):
        """
        Post Components to the database.

        `new_values`    dictionary {name~>value}
        """
        if self.current_avg_endpoint is None:
            raise Exception("create average first")
    
        payload = {
            "quantities": [
                {
                    "componentID": self.get_component(name)["componentID"],
                    "value": value
                } for name, value in new_values.items()
            ]
        }
        endpoint = self.current_avg_endpoint + '/component_traces'
        self.put(endpoint, payload)

    def save_instrument_values(self, new_values):
        """
        Post Parameters to the database.

        `new_values`    dictionary {name~>value}
        """
        # 13.07.: SCHNELL, SCHNELL (es ist 17 Uhr 57 und ich will die Modbus-instrument
        #  daten noch hochladen):
        #  this expects a namedtuple as defined in Modbus client: .set, .act, .par_id
        if self.current_avg_endpoint is None:
            raise Exception("create average first")
    
        payload = {
            "quantities": [
                {
                    "parameterID": item.par_id,
                    "setValue": item.set,
                    "actMean": item.act
                } for name, item in new_values.items()
            ]
        }
        endpoint = self.current_avg_endpoint + '/parameter_traces'  # on the DB it's called parameter... :\
        self.put(endpoint, payload)

