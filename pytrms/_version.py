__version__ = '0.2.2'  # must be on the first line!

__all__ = ['branch', 'digest', '__version__']


from os.path import abspath, dirname, join, isdir

# 'gitdir' might be defined by the setup.py script..
if not 'gitdir' in vars():
    gitdir = abspath(join(dirname(__file__), '..', '.git'))

# in development mode: get git branch and digest..
if isdir(gitdir):
    with open(join(gitdir, 'HEAD')) as f:
        refinfo = f.readline().strip()
        detached = not refinfo.startswith('ref:')
        if detached:
            branch = 'detached-HEAD'
            digest = refinfo[:7]
        else:
            refpath = refinfo.split()[-1]
            branch = refinfo.split('/')[-1]
            digest = open(join(gitdir, refpath)).read(7)

    if not branch == 'master':
        __version__ += '.dev' + str(eval('0x'+digest))
