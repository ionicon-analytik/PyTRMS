import os

__all__ = []


from .ioniclient import IoniClient

__all__ += ['IoniClient']

ionitof_host = str(os.environ.get('IONITOF_HOST', '127.0.0.1'))
ionitof_port = int(os.environ.get('IONITOF_PORT', 8002))
ionitof_url = f'http://{ionitof_host}:{ionitof_port}'

database_host = str(os.environ.get('DATABASE_HOST', '127.0.0.1'))
database_port = int(os.environ.get('DATABASE_PORT', 5066))
database_url = f'http://{database_host}:{database_port}'

