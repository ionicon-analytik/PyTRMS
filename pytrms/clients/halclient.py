import os
import json
from contextlib import contextmanager
import logging

import requests

from . import database_url

log = logging.getLogger()


class HALClient:

    def __init__(self, url='', session=None):
        if not url:
            url = database_url

        if session is None:
            session = requests.sessions.Session()

        self.url = url
        self.session = session

    def create_object(self, endpoint, payload):
        data = json.dumps(payload)
        r = self.session.post(self.url + endpoint, data=data, headers={
            'content-type': 'application/hal+json'}
        )
        if not r.ok:
            log.error(f"POST {endpoint}\n{data}\n\n"
                      f"returned [{r.status_code}]: {r.content}")
            r.raise_for_status()

        return r.headers['Location']

    def create_average(self, run, step, use_mean=True):
        return self.create_object('/api/averages', payload={
          "_embedded": {
            "automation": {
              "AUTO_StepNumber": 0,
              "AUTO_RunNumber": 0,
              "AUTO_UseMean": bool(use_mean),
              "AUTO_StartCycleMean": 0,
              "AUTO_StopCycleMean": 0,
              "AME_ActionNumber": 0,
              "AME_UserNumber": 0,
              "AME_StepNumber": int(step),
              "AME_RunNumber": int(run),
            }
          }
        })

    def create_timecycle(self, rel_cycle, abs_cycle, abs_time, rel_time, sourcefile_path, automation):
        return self.create_object('/api/times', payload={
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
