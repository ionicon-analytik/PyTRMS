import os
import json
from contextlib import contextmanager
import logging

import requests

from . import database_url

log = logging.getLogger()

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

    def refresh_comp_dict(self):
        r = self.session.get(self.url + '/api/components',
                    headers={'content-type': 'application/hal+json'})
        r.raise_for_status()
        j = r.json()
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
        self._create_object('/api/components', payload)
        self.refresh_comp_dict()

    def create_average(self, run, step, action=0, use_mean=True):
        payload = {
            "_embedded": {
                "automation": {
                    "AUTO_StepNumber": 0,
                    "AUTO_RunNumber": 0,
                    "AUTO_UseMean": bool(use_mean),
                    "AUTO_StartCycleMean": 0,
                    "AUTO_StopCycleMean": 0,
                    "AME_ActionNumber": int(action),
                    "AME_UserNumber": 0,
                    "AME_StepNumber": int(step),
                    "AME_RunNumber": int(run),
                }
            }
        }
        self.current_avg_endpoint = self._create_object('/api/averages', payload)

    def create_timecycle(self, rel_cycle, abs_cycle, abs_time, rel_time,
            sourcefile_path, automation):
        self._create_object('/api/times', payload={
            "RelCycle": int(rel_cycle),
            "AbsCycle": int(abs_cycle),
            "AbsTime": float(abs_time),
            "RelTime": float(rel_time),
            "_embedded": {
                "sourcefile": {
                    "path": str(sourcefile_path),
                },
                "automation": dict(automation)
            }
        })

    def save_component_values(self, new_values):
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
        self._create_object(endpoint, payload, method='put')

    def save_instrument_values(self, new_instrument_values):
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
                } for name, item in new_instrument_values.items()
            ]
        }
        endpoint = self.current_avg_endpoint + '/parameter_traces'  # on the DB it's called parameter... :\
        self._create_object(endpoint, payload, method='put')

    def _create_object(self, endpoint, payload, method='post'):
        data = json.dumps(payload)
        r = self.session.request(method, self.url + endpoint, data=data,
            headers={'content-type': 'application/hal+json'})
        if not r.ok:
            log.error(f"POST {endpoint}\n{data}\n\n"
                      f"returned [{r.status_code}]: {r.content}")
            r.raise_for_status()

        return r.headers.get('Location')

