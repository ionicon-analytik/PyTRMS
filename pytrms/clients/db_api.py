import os
import time
import json
import logging
from collections import namedtuple
import urllib3.util

import requests
import requests.adapters
import requests.exceptions

from .ssevent import SSEventListener
from .._base import _IoniClientBase

log = logging.getLogger(__name__)

_unsafe = namedtuple('http_response', ['status_code', 'href'])

__all__ = ['IoniConnect']


class IoniConnect(_IoniClientBase):

    # Note: this retry-policy is specifically designed for the
    #  SQLite Error 5: 'database locked', which may take potentially
    #  minutes to resolve itself! Therefore, it is extra generous
    #  and backs off up to `3.0 * 2^4 = 48 sec` between retries for
    #  a total of ~1 1/2 minutes (plus database timeout). But, giving
    #  up on retrying here, would mean *losing all data* in the queue!
    #    ==>> We would rather crash on a `queue.full` exception! <<==
    _retry_policy = urllib3.util.Retry(
        # this configures policies on each cause for errors individually...
        total=None,             # max. retries (takes precedence). `None`: turned off
        connect=0, read=0, redirect=0,  # (all turned off, see docs for details)
        other=0,                # "other" errors include timeout (set to 27 seconds)
        # configure the retries on specific status-codes...
        status=5,               # how many times to retry on bad status codes
        raise_on_status=True,   # `True`: do not return a 429 status code
        status_forcelist=[429], # integer status-codes to retry on
        allowed_methods=None,   # `None`: retry on all (possibly not idempotent) verbs
        # this configures backoff between retries...
        backoff_factor=3.0,     # back off *after* first try in seconds (x 2^n_retries)
        respect_retry_after_header=False,  # would override `backoff_factor`, turn off!
    )

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
            self.get_location("/api/measurements/current")
            return True
        except (AssertionError, requests.exceptions.HTTPError):
            return False

    def connect(self, timeout_s=10):
        self.session = requests.sessions.Session()
        self.session.mount('http://',  self._http_adapter)
        self.session.mount('https://', self._http_adapter)
        try:
            self.current_meas_loc = self.get_location("/api/measurements/current")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 410:  # Gone
                # OK, no measurement running..
                self.current_meas_loc = ''
                return
        except requests.exceptions.ConnectionError as e:
            self.session = self.current_meas_loc = None
            log.error(type(e).__name__, str(e))
            raise

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
        loc = self.current_meas_loc or self.get_location("/api/measurements/current")
        self.patch(loc, { "isRunning": False })
        self.current_meas_loc = ''

    def __init__(self, host='127.0.0.1', port=5066):
        super().__init__(host, port)
        self.url = f"http://{self.host}:{self.port}"
        self._http_adapter = requests.adapters.HTTPAdapter(max_retries=self._retry_policy)
        self.session = None
        self.current_meas_loc = None
        try:
            self.connect(timeout_s=3.3)
        except requests.exceptions.ConnectionError:
            log.warning("no connection! make sure the DB-API is running and try again")

    def get(self, endpoint, **kwargs):
        """Make a GET request to `endpoint` and parse JSON if applicable."""
        try:
            r = self._fetch_object(endpoint, 'get', **kwargs)
            if 'json' in r.headers.get('content-type', ''):
                return r.json()
            if 'text' in r.headers.get('content-type', ''):
                return r.text
            else:
                log.warning(f"unexpected 'content-type: {r.headers['content-type']}'")
                log.info(f"did you mean to use `{type(self).__name__}.download(..)` instead?")
                return r.content

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 410:  # Gone
                log.debug(f"nothing there at '{endpoint}' 0_o ?!")
                return None
            raise

    def get_location(self, endpoint, **kwargs):
        """Returns the actual location that `endpoint` points to (may be a redirect)."""
        r = self._fetch_object(endpoint, 'get', **(kwargs | { "allow_redirects": False }))
        return r.headers.get('Location', r.request.path_url)

    def post(self, endpoint, data, **kwargs):
        """Append to the collection at `endpoint` the object defined by `data`."""
        r = self._create_object(endpoint, data, 'post', **kwargs)
        return _unsafe(r.status_code, r.headers.get('Location', ''))  # no default location known!

    def put(self, endpoint, data, **kwargs):
        """Replace the entire object at `endpoint` with `data`."""
        r = self._create_object(endpoint, data, 'put', **kwargs)
        return _unsafe(r.status_code, r.headers.get('Location', r.request.path_url))

    def patch(self, endpoint, data, **kwargs):
        """Change parts of the object at `endpoint` with fields in `data`."""
        r = self._create_object(endpoint, data, 'patch', **kwargs)
        return _unsafe(r.status_code, r.headers.get('Location', r.request.path_url))

    def delete(self, endpoint, **kwargs):
        """Attempt to delete the object at `endpoint`."""
        r = self._fetch_object(endpoint, 'delete', **kwargs)
        return _unsafe(r.status_code, r.headers.get('Location', r.request.path_url))

    def link(self, parent_ep, child_ep, **kwargs):
        """Make the object at `parent_e[nd]p[oint]` refer to `child_e[nd]p[oint]`"""
        r = self._make_link(parent_ep, child_ep, sever=False, **kwargs)
        return _unsafe(r.status_code, r.headers.get('Location', r.request.path_url))

    def unlink(self, parent_ep, child_ep, **kwargs):
        """Destroy the reference from `parent_e[nd]p[oint]` to `child_e[nd]p[oint]`"""
        r = self._make_link(parent_ep, child_ep, sever=True, **kwargs)
        return _unsafe(r.status_code, r.headers.get('Location', r.request.path_url))

    def upload(self, endpoint, filename):
        """Upload the file at `filename` to `endpoint`."""
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        with open(filename, 'rb') as f:
            # Note (important!): this is a "form-data" entry, where the server
            #  expects the "name" to be 'file' and rejects it otherwise:
            name = 'file'
            r = self._create_object(endpoint, None, 'post',
                    # Note: the requests library will set the content-type automatically
                    #  and also add a randomly generated "boundary" to separate files:
                    #headers={'content-type': 'multipart/form-data'}, No!
                    files=[(name, (filename, f, ''))])
            r.raise_for_status()

        return _unsafe(r.status_code, r.headers.get('Location', r.request.path_url))

    def download(self, endpoint, out_file='.'):
        """Download from `endpoint` into `out_file` (may be a directory).

        Returns:
            status_code, actual_filename
        """
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        out_file = os.path.abspath(out_file)

        content_type = 'application/octet-stream'
        r = self._fetch_object(endpoint, 'get', stream=True, headers={'accept': content_type})
        assert r.headers['content-type'] == content_type, "unexcepted content-type"

        content_dispo = r.headers['content-disposition'].split('; ')
        #['attachment',
        # 'filename=2025_10_06__13_23_32.h5',
        # "filename*=UTF-8''2025_10_06__13_23_32.h5"]
        filename = next(
            (dispo.split('=')[1] for dispo in content_dispo if dispo.startswith("filename="))
            , None)
        if os.path.isdir(out_file):
            assert filename, "no out_file given and server didn't supply filename"
            out_file = os.path.join(out_file, filename)

        with open(out_file, mode='xb') as f:
            # chunk_size must be of type int or None. A value of None will
            # function differently depending on the value of `stream`.
            # stream=True will read data as it arrives in whatever size the
            # chunks are received. If stream=False, data is returned as
            # a single chunk.
            for chunk in r.iter_content(chunk_size=None):
                f.write(chunk)
            r.close()

        return _unsafe(r.status_code, out_file)

    def _fetch_object(self, endpoint, method='get', **kwargs):
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        if 'headers' not in kwargs:
            kwargs['headers'] = {'accept': 'application/json'}
        elif 'accept' not in (k.lower() for k in kwargs['headers']):
            kwargs['headers'].update({'accept': 'application/json'})
        if 'timeout' not in kwargs:
            # https://requests.readthedocs.io/en/latest/user/advanced/#timeouts
            kwargs['timeout'] = (6.06, 27)
        r = self.session.request(method, self.url + endpoint, **kwargs)
        r.raise_for_status()

        return r

    def _make_link(self, parent_href, child_href, *, sever=False, **kwargs):
        if not parent_href.startswith('/'):
            parent_href = '/' + parent_href
        if not child_href.startswith('/'):
            child_href = '/' + child_href
        if 'headers' not in kwargs:
            kwargs['headers'] = {'location': child_href}
        else:
            kwargs['headers'].update({'location': child_href})
        if 'timeout' not in kwargs:
            # https://requests.readthedocs.io/en/latest/user/advanced/#timeouts
            kwargs['timeout'] = (6.06, 27)
        r = self.session.request("LINK" if not sever else "UNLINK",
                self.url + parent_href, **kwargs)
        r.raise_for_status()

        return r

    def _create_object(self, endpoint, data, method='post', **kwargs):
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        if data is not None:
            if not isinstance(data, str):
                # Note: default is `ensure_ascii=True`, but this escapes Umlaute!
                data = json.dumps(data, ensure_ascii=False)
            if 'headers' not in kwargs:
                kwargs['headers'] = {'content-type': 'application/json'}
            elif 'content-type' not in (k.lower() for k in kwargs['headers']):
                kwargs['headers'].update({'content-type': 'application/json'})
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
        pt_server = self.get('/api/peaks')['_embedded']['peaks']
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
            else:
                self.put(db_peaks[key]['self']['href'], updates[key]['payload'])
                log.info(f"updated:    {key}")
                updated += 1

        if len(to_upload):
            # Note: POSTing the embedded-collection is *miles faster*
            #  than doing separate requests for each peak!
            payload = {
                '_embedded': {
                    'peaks': [updates[key]['payload']
                              for key in sorted(to_upload)]
                }
            }
            self.post('/api/peaks', payload)
            for key in sorted(to_upload):
                log.info(f"added new:  {key}")
            # Note: we need the updated peaktable to learn about 
            #  the href (id) assigned to newly added peaks:
            pt_server = self.get('/api/peaks')['_embedded']['peaks']

        log.info("repairing fitpeak~>nominal links...")
        peak2href = {
            Peak(p["center"], label=p["name"]): p["_links"]["self"]["href"]
            for p in pt_server
        }
        to_link = set((peak2href[fitted], peak2href[fitted.parent])
            for fitted in peaktable.fitted)

        is_link = set((child["_links"]["self"]["href"], child["_links"]["parent"]["href"])
            for child in pt_server if "parent" in child["_links"])

        for child_href, parent_href in is_link & to_link:
            log.debug(f"keep link  {parent_href} <~> {child_href}")
            pass

        for child_href, parent_href in to_link - is_link:
            log.debug(f"make link  {parent_href} ~>> {child_href}")
            self.link(parent_href, child_href)

        for child_href, parent_href in is_link - to_link:
            log.debug(f'break link {parent_href} ~x~ {child_href}')
            self.unlink(parent_href, child_href)

        return {
                'added': len(to_upload),
                'updated': updated,
                'up-to-date': up_to_date,
                'linked': len(to_link - is_link),
                'unlinked': len(is_link - to_link),
        }

    def iter_events(self, event_re=r".*"):
        """Follow the server-sent-events (SSE) on the DB-API.

        `event_re`  a regular expression to filter events (default: matches everything)

        Note: This will block until a matching event is received.
         Especially, it cannot be cancelled by KeyboardInterrupt (due to the `requests`
         stream-implementation), unless the server sends a keep-alive at regular
         intervals (as every well-behaved server should be doing)!
        """
        # Note: DO NOT inject our `requests.session` with the 'session' kw-arg!!
        #  For some unknown reason this didn't work. Maybe in combination with
        #  the new _http_adapter? Who knows.. let the listener use its own session:
        yield from SSEventListener(event_re, host_url=self.url, endpoint="/api/events")

