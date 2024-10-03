import os
import json
from contextlib import contextmanager
import logging

import requests

from . import ionitof_url

log = logging.getLogger()


class Template:
    '''A template for uploading a collection item.

    >>> t = Template()
    >>> t.template == Template.default_template
    True

    >>> t.render('AME_FooNumber', 42)
    '{"template": {"data": [{"name": "ParaID", "value": "AME_FooNumber", "prompt": "the
        parameter ID"}, {"name": "ValAsString", "value": "42", "prompt": "the new value"}]}}'

    '''

    default_template = {
            "data": [
                 {"name": "ParaID", "value": "AME_RunNumber", "prompt": "the parameter ID"},
                 {"name": "ValAsString", "value": "5.000000", "prompt": "the new value"},
                 {"name": "DataType", "value": "", "prompt": "datatype (int, float, string)"},
             ]
         }

    @staticmethod
    def download(url=ionitof_url, endpoint='/api/schedule'):
        r = requests.get(url + endpoint, headers={'accept': 'application/vnd.collection+json'})
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
            if 'typ' in insert["name"].lower() or 'datatype' in insert["prompt"]:
                self._inserts["dtype"] = insert

        assert len(self._inserts) == 3, "missing or unknown name in template"

    def render(self, parID, value):
        """Prepare a request for uploading."""
        dtype = 'float'
        if isinstance(value, int): dtype = 'int'
        if isinstance(value, str): dtype = 'string'

        parID_insert = dict(self._inserts["parID"])
        value_insert = dict(self._inserts["value"])
        dtype_insert = dict(self._inserts["dtype"])

        parID_insert.update(value=str(parID)),
        value_insert.update(value=str(value)),
        dtype_insert.update(value=str(dtype)),

        return json.dumps({
            "template": dict(data=[
                parID_insert,
                value_insert,
                dtype_insert,
            ])}
        )

    def render_many(self, new_values):
        for key, value in new_values.items():
            yield self.render(key, value)


class Dirigent:

    def __init__(self, url=ionitof_url, template=None):
        if template is None:
            template = Template.download(url)

        self.url = url
        self.template = template
        self._session = None  # TODO :: ?

    def push(self, parID, new_value, future_cycle):
        uri = self.url + '/api/schedule/' + str(int(future_cycle))
        payload = self.template.render(parID, new_value)
        r = self._make_request('PUT', uri, payload=payload)

        return r.status_code

    def push_filename(self, path, future_cycle):
        return self.push('ACQ_SRV_SetFullStorageFile', path.replace('/', '\\'), future_cycle - 2)

    def find_scheduled(self, parID):
        uri = self.url + '/api/schedule/search'
        r = self._make_request('GET', uri, params={'name': str(parID)})
        j = r.json()

        return [item['href'].split('/')[-1] for item in j['collection']['items']]

    def _make_request(self, method, uri, params=None, payload=None):
        if self._session is None:
            session = requests  # not using a session..
        else:
            session = self._session

        try:
            r = session.request(method, uri, params=params, data=payload, headers={
                'content-type': 'application/vnd.collection+json'
            })
        except requests.exceptions.ConnectionError as exc:
            # Note: the LabVIEW-webservice seems to implement a weird HTTP:
            #  we may get a [85] Custom Error (Bad status line) from urllib3
            #  even though we just mis-spelled a parameter-ID ?!
            log.error(exc)
            raise KeyError(str(params, payload))

        log.debug(f"request to <{uri}> returned [{r.status_code}]")
        if not r.ok and payload:
            log.error(payload)
        r.raise_for_status()

        return r

    def wait_until(self, future_cycle):
        if self._session is None:
            session = requests  # not using a session..
        else:
            session = self._session

        r = session.get(self.url + '/api/timing/' + str(int(future_cycle)))
        # ...
        if r.status_code == 410:
            # 410 Client Error: Gone 
            log.warning("we're late, better return immediately!")
            return r.status_code
    
        r.raise_for_status()
        log.debug(f"waited until {r.json()['TimeCycle']}")

        return r.status_code

    @contextmanager
    def open_session(self):
        '''open a session for faster upload (to be used as a contextmanager).'''
        if self._session is None:
            self._session = requests.Session()
        try:
            yield self
        finally:
            self._session.close()
            self._session = None


if __name__ == '__main__':
    import doctest
    doctest.testmod(verbose=True, optionflags=doctest.ELLIPSIS)

