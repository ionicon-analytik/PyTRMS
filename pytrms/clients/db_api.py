import os
import time
import json
import logging

import requests

from .ssevent import SSEventListener
from .._base import _IoniClientBase

log = logging.getLogger(__name__)


class IoniConnect(_IoniClientBase):

    @property
    def is_connected(self):
        '''Returns `True` if connection to IoniTOF could be established.'''
        try:
            assert self.session is not None, "not connected"
            self.get("/api/status")
            return True
        except:
            return False

    @property
    def is_running(self):
        '''Returns `True` if IoniTOF is currently acquiring data.'''
        try:
            assert self.session is not None, "not connected"
            self._get_location("/api/measurements/current")
            return True
        except (AssertionError, requests.exceptions.HTTPError):
            return False

    def connect(self, timeout_s=10):
        self.session = requests.sessions.Session()
        started_at = time.monotonic()
        while timeout_s is None or time.monotonic() < started_at + timeout_s:
            try:
                self.current_meas_loc = self._get_location("/api/measurements/current")
                break
            except requests.exceptions.HTTPError:
                # OK, no measurement running..
                self.current_meas_loc = ''
                break
            except Exception:
                pass

            time.sleep(10e-1)
        else:
            self.session = self.current_meas_loc = None
            raise TimeoutError(f"no connection to '{self.url}'");

    def disconnect(self):
        if self.session is not None:
            del self.session
            self.session = None
            self.current_meas_loc = None

    def start_measurement(self, path=None):
        '''Start a new measurement and block until the change is confirmed.

        If 'path' is not None, write to the given .h5 file.
        '''
        assert not self.is_running, "measurement already running @ " + str(self.current_meas_loc)

        payload = {}
        if path is not None:
            assert os.path.isdir(path), "must point to a (recipe-)directory: " + str(path)
            payload |= { "recipeDirectory": str(path) }

        self.current_meas_loc = self.post("/api/measurements", payload)
        self.put(self.current_meas_loc, { "isRunning": True })

        return self.current_meas_loc

    def stop_measurement(self, future_cycle=None):
        '''Stop the current measurement and block until the change is confirmed.

        If 'future_cycle' is not None and in the future, schedule the stop command.
        '''
        loc = self.current_meas_loc or self._get_location("/api/measurements/current")
        self.put(loc, { "isRunning": False })
        self.current_meas_loc = ''

    def __init__(self, host='127.0.0.1', port=5066):
        super().__init__(host, port)
        self.url = f"http://{self.host}:{self.port}"
        self.session = None
        self.current_meas_loc = None
        try:
            self.connect(timeout_s=3.3)
        except TimeoutError:
            log.warning("no connection! make sure the DB-API is running and try again")

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
        if 'timeout' not in kwargs:
            # https://requests.readthedocs.io/en/latest/user/advanced/#timeouts
            kwargs['timeout'] = (6.06, 27)
        r = self.session.request('get', self.url + endpoint, **kwargs)
        r.raise_for_status()

        return r

    def _get_location(self, endpoint, **kwargs):
        r = self._get_object(endpoint, **(kwargs | { "allow_redirects": False }))

        return r.headers.get('Location')

    def _create_object(self, endpoint, data, method='post', **kwargs):
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        if not isinstance(data, str):
            data = json.dumps(data, ensure_ascii=False)  # default is `True`, escapes Umlaute!
        if 'headers' not in kwargs:
            kwargs['headers'] = {'content-type': 'application/hal+json'}
        elif 'content-type' not in (k.lower() for k in kwargs['headers']):
            kwargs['headers'].update({'content-type': 'application/hal+json'})
        if 'timeout' not in kwargs:
            # https://requests.readthedocs.io/en/latest/user/advanced/#timeouts
            kwargs['timeout'] = (6.06, 27)
        r = self.session.request(method, self.url + endpoint, data=data, **kwargs)
        if not r.ok:
            log.error(f"POST {endpoint}\n{data}\n\nreturned [{r.status_code}]: {r.content}")
            r.raise_for_status()

        return r

    def sync(self, peaktable):
        """Compare and upload any differences in `peaktable` to the database."""
        from pytrms.peaktable import Peak, PeakTable
        from operator import attrgetter

        # Note: the DB-API distinguishes between peaks with 
        #  different center *and* name, while the PyTRMS 'Peak'
        #  only distinguishes by center, so this is our key:
        make_key = lambda p_info: (p_info['center'], p_info['name'])

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
            'resolution': attrgetter('resolution'),
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
        updated = up_to_date = 0
        for key in sorted(to_update):
            # check if an existing peak needs an update
            if db_peaks[key]['payload'] == updates[key]['payload']:
                # nothing to do..
                log.debug(f"up-to-date: {key}")
                up_to_date += 1
                continue

            self.put(db_peaks[key]['self']['href'], updates[key]['payload'])
            log.info(f"updated:    {key}")
            updated += 1

        if len(to_upload):
            # Note: POSTing the embedded-collection is *miles faster*
            #  than doing separate requests for each peak!
            payload = {'_embedded': {'peaks': [updates[key]['payload'] for key in sorted(to_upload)]}}
            self.post('/api/peaks', payload)
            for key in sorted(to_upload):
                log.info(f"added new:  {key}")

        linked = unlinked = 0
        for child in self.get("/api/peaks?only=children")["_embedded"]["peaks"]:
            # clear all children (a.k.a. fitpeaks)...
            child_href = child["_links"]["self"]["href"]
            parent_href = child["_links"]["parent"]["href"]
            r = self.session.request('unlink', self.url + parent_href,
                    headers={"location": child_href})
            if not r.ok:
                log.error(f'UNLINK {child_href} from Location: {parent_href}'
                        + f'\n\nfailed with [{r.status_code}]: {r.content}')
                r.raise_for_status()
            log.debug(f'unlinked parent {parent_href} ~x~ {child_href}')
            unlinked += 1

        if len(peaktable.fitted):
            # Note: until now, we disregarded the peak-parent-relationship, so
            #  make another request to the updated peak-table from the server...
            pt_updated = self.get('/api/peaks')['_embedded']['peaks']
            peak2href = {
                Peak(p["center"], label=p["name"]): p["_links"]["self"]["href"]
                for p in pt_updated
            }
            for fitted in peaktable.fitted:
                fitted_href = peak2href[fitted]
                parent_href = peak2href[fitted.parent]
                r = self.session.request('link', self.url + parent_href,
                        headers={"location": fitted_href})
                if not r.ok:
                    log.error(f"LINK {parent_href} to Location: {fitted_href}"
                            + f"\n\nfailed with [{r.status_code}]: {r.content}")
                    r.raise_for_status()
                log.debug(f"linked parent {parent_href} ~~> {fitted_href}")
                linked += 1

        return {
                'added': len(to_upload),
                'updated': updated,
                'up-to-date': up_to_date,
                'linked': linked,
                'unlinked': unlinked,
        }

    def iter_events(self, event_re=r".*"):
        """Follow the server-sent-events (SSE) on the DB-API.

        `event_re`  a regular expression to filter events (default: matches everything)

        Note: This will block until a matching event is received.
         Especially, it cannot be cancelled by KeyboardInterrupt (due to the `requests`
         stream-implementation), unless the server sends a keep-alive at regular
         intervals (as every well-behaved server should be doing)!
        """
        yield from SSEventListener(event_re, host_url=self.url, endpoint="/api/events",
                session=self.session)

