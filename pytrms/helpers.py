import requests.exceptions

class PTRConnectionError(requests.exceptions.ConnectionError):
    pass


