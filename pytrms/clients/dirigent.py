import os
import json
from contextlib import contextmanager
import logging

log = logging.getLogger()

import requests

from . import ionitof_url


class Template:
    '''A template for updloading a collection item.

    >>> t = Template()
    >>> t.template == Template.default_template
    True

    >>> t.render('AME_FooNumber', 42)
    '{"template": {"data": [{"name": "ParaID", "value": "AME_FooNumber", "prompt": "the
        parameter ID"}, {"name": "ValAsString", "value": "42", "prompt": "the new value"}]}}'

    '''

    default_template = {
            "data": [
                 { "name": "ParaID", "value": "AME_RunNumber", "prompt": "the parameter ID" },
                 { "name": "ValAsString", "value": "5.000000", "prompt": "the new value" },
             ]
         }

    @staticmethod
    def download(url=ionitof_url, endpoint='/api/schedule'):
        r = requests.get(url + endpoint,
                headers={'accept': 'application/vnd.collection+json'})
        r.raise_for_status()
        j = r.json()

        return Template(j["collection"]["template"])

    def __init__(self, template=None):
        if template is None:
            template = Template.default_template
        self.template = dict(template)

        self._inserts = dict()  # cache data-items sorted by semantic meaning..
        for insert in self.template["data"]:
            if 'ID' in insert["name"] or 'parameter' in insert["prompt"]:
                self._inserts["parID"] = insert
            if 'set' in insert["name"].lower() or 'value' in insert["prompt"]:
                self._inserts["value"] = insert

        assert len(self._inserts) == 2, "missing or unknown name in template"

    def render(self, parID, value):
        parID_insert = dict(self._inserts["parID"])
        value_insert = dict(self._inserts["value"])

        parID_insert.update(value=parID),
        value_insert.update(value=str(value)),

        return json.dumps(
            { "template": dict(data=[
                parID_insert,
                value_insert,
            ])}
        )

    def render_many(self, new_values):
        for key, value in new_values.items():
            yield render(key, value)


class Dirigent:

    method = 'PUT'

    def __init__(self, url=ionitof_url, template=None):
        if template is None:
            template = Template.download(url)

        self.url = url
        self.template = template
        self._session = None

    def push(self, parID, new_value, future_cycle):
        if self._session is None:
            session = requests  # not using a session..
        else:
            session = self._session
        
        uri = self.url + '/api/schedule/' + str(int(future_cycle))
        payload = self.template.render(parID, new_value)
        r = session.request(self.method, uri, data=payload,
                headers={'content-type': 'application/vnd.collection+json'})
        log.debug(f'got [{r.status_code}]')
        if not r.ok:
            log.error(payload)
        r.raise_for_status()

    def wait_until(self, future_cycle):
        if self._session is None:
            session = requests  # not using a session..
        else:
            session = self._session

        r = session.get(self.url + '/api/timing/' + str(int(future_cycle)))
        # ...
        if (r.status_code == 410):
            # 410 Client Error: Gone 
            log.warn("we're late, better return immediately!")
            return
    
        r.raise_for_status()
        log.debug(str(r.json()["TimeCycle"]))

    @contextmanager
    def open_session(self):
        '''open a session for faster upload (to be used as a contextmanager).'''
        if self._session is None:
            self._session = requests.Session()
        try:
            # ready to accept more input..
            yield self
        finally:
            self._session.close()
            self._session = None


if __name__ == '__main__':
    import doctest
    doctest.testmod(verbose=True, optionflags=doctest.ELLIPSIS)

