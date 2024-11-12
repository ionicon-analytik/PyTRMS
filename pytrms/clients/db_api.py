import os
import json

import requests

from . import _logging
from .ssevent import SSEventListener
from .._base import IoniClientBase

log = _logging.getLogger(__name__)

# TODO :: sowas waer auch ganz cool: die DBAPI bietes sich geradezu an,
#  da mehr object-oriented zu arbeiten:
#   currentVariable = get_component(currentComponentNameAction, ds)
#   currentVariable.save_value({'value': currentValue})

class IoniConnect(IoniClientBase):

    @property
    def is_connected(self):
        '''Returns `True` if connection to IoniTOF could be established.'''
        try:
            self.get("/api/status")
            return True
        except:
            return False

    @property
    def is_running(self):
        '''Returns `True` if IoniTOF is currently acquiring data.'''
        raise NotImplementedError("is_running")

    def connect(self, timeout_s):
        pass

    def disconnect(self):
        pass

    def __init__(self, host='127.0.0.1', port=5066, session=None):
        super().__init__(host, port)
        self.url = f"http://{self.host}:{self.port}"
        if session is None:
            session = requests.sessions.Session()
        self.session = session
        # ??
        self.current_avg_endpoint = None
        self.comp_dict = dict()

    def get(self, endpoint, **kwargs):
        return self._get_object(endpoint, **kwargs).json()

    def post(self, endpoint, data, **kwargs):
        return self._create_object(endpoint, data, 'post', **kwargs).headers.get('Location')

    def put(self, endpoint, data, **kwargs):
        return self._create_object(endpoint, data, 'put', **kwargs).headers.get('Location')

    def upload(self, endpoint, filename):
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        with open(filename) as f:
            # Note (important!): this is a "form-data" entry, where the server
            #  expects the "name" to be 'file' and rejects it otherwise:
            name = 'file'
            r = self.session.post(self.url + endpoint, files=[(name, (filename, f, ''))])
            r.raise_for_status()

        return r

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
            data = json.dumps(data, ensure_ascii=False)  # default is `True`, escapes Umlaute!
        if 'headers' not in kwargs:
            kwargs['headers'] = {'content-type': 'application/hal+json'}
        elif 'content-type' not in (k.lower() for k in kwargs['headers']):
            kwargs['headers'].update({'content-type': 'application/hal+json'})
        r = self.session.request(method, self.url + endpoint, data=data, **kwargs)
        if not r.ok:
            log.error(f"POST {endpoint}\n{data}\n\nreturned [{r.status_code}]: {r.content}")
            r.raise_for_status()

        return r

    def sync(self, peaktable):
        """Compare and upload any differences in `peaktable` to the database."""
        from pytrms.peaktable import Peak, PeakTable
        from operator import attrgetter

        # Note: a `Peak` is a hashable object that serves as a key that
        #  distinguishes between peaks as defined by PyTRMS:
        make_key = lambda peak: Peak(center=peak['center'], label=peak['name'], shift=peak['shift'])

        if isinstance(peaktable, str):
            log.info(f"loading peaktable '{peaktable}'...")
            peaktable = PeakTable.from_file(peaktable)

        # get the PyTRMS- and IoniConnect-peaks on the same page:
        conv = {
            'name':   attrgetter('label'),
            'center': attrgetter('center'),
            'kRate':  attrgetter('k_rate'),
            'low':    lambda p: p.borders[0],
            'high':   lambda p: p.borders[1],
            'shift':  attrgetter('shift'),
            'multiplier': attrgetter('multiplier'),
        }
        # normalize the input argument and create a hashable set:
        updates = dict()
        for peak in peaktable:
            payload = {k: conv[k](peak) for k in conv}
            updates[make_key(payload)] = {'payload': payload}

        log.info(f"fetching current peaktable from the server...")
        # create a comparable collection of peaks already on the database by
        # reducing the keys in the response to what we actually want to update:
        db_peaks = {make_key(p): {
                    'payload': {k: p[k] for k in conv.keys()},
                    'self':   p['_links']['self'],
                    'parent': p['_links'].get('parent'),
                    } for p in self.get('/api/peaks')['_embedded']['peaks']}

        to_update = updates.keys() & db_peaks.keys()
        to_upload = updates.keys() - db_peaks.keys()
        updated = 0
        for key in sorted(to_update):
            # check if an existing peak needs an update
            if db_peaks[key]['payload'] == updates[key]['payload']:
                # nothing to do..
                log.debug(f"up-to-date: {key}")
                continue

            self.put(db_peaks[key]['self']['href'], updates[key]['payload'])
            log.info(f"updated:    {key}")
            updated += 1

        if len(to_upload):
            # Note: POSTing the embedded-collection is *miles faster*
            #  than doing separate requests for each peak!
            payload = {'_embedded': {'peaks': [updates[key]['payload'] for key in sorted(to_upload)]}}
            self.post('/api/peaks', payload)
            for key in sorted(to_upload): log.info(f"added new:  {key}")

        # Note: this disregards the peak-parent-relationship, but in
        #  order to implement this correctly, one would need to check
        #  if the parent-peak with a specific 'parentID' is already
        #  uploaded and search it.. there's an endpoint
        #   'LINK /api/peaks/{parentID} Location: /api/peaks/{childID}'
        #  to link a child to its parent, but it remains complicated.
        # TODO :: maybe later implement parent-peaks!?

        return {
                'added': len(to_upload),
                'updated': updated,
                'up-to-date': len(to_update) - updated,
        }

    def iter_events(self, event_re=r".*"):
        """Follow the server-sent-events (SSE) on the DB-API.

        `event_re`  a regular expression to filter events (default: matches everything)
        """
        yield from SSEventListener(event_re, host_url=self.url, endpoint="/api/events",
                session=self.session)

