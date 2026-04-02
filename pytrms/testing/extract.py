import os
import re
import shutil
import zipfile
import tempfile


def extractdir(file, arcname, dest, force=False):
    '''extract an archived directory under `arcname` to `dest`.

    if `force=False`, the `dest[ination]` must not exist!
    otherwise, it will be completely overwritten!
    '''
    if os.path.isdir(dest):
        if force:
            shutil.rmtree(dest)
        else:
            raise FileExistsError(dest)

    with tempfile.TemporaryDirectory() as tempdir_name:
        with zipfile.ZipFile(file, 'r') as z:
            arc_members = [s for s in z.namelist() if s.startswith(arcname)]
            z.extractall(path=tempdir_name, members=arc_members)
        src = tempdir_name + '/' + arcname
        # (a format-string w/ side-effect?! what could go wrong?)
        print(f'{ shutil.move(src, dest) = }')


def extractpaths(replay_file, arcname='sources/'):
    '''extract archived paths under `arcname` to a different absolute location.

    this assumes that the `replay_file` (zip-archive) encodes the absolute paths
    underneath the given `arcname` as starting with a driveletter! For example,
    'sources/d/AMEData/foo.h5' will be extracted to 'D:\\AMEData\\foo.h5'.
    '''
    arcname = arcname if arcname.endswith('/') else arcname + '/'
    with tempfile.TemporaryDirectory() as tempdir_name:
        root = tempdir_name + '/' + arcname
        with zipfile.ZipFile(replay_file, 'r') as z:
            # match e.g. 'sources/d/AMEData/..' with a '/./' driveletter:
            regex = re.compile('^' + arcname + './')
            arc_members = [s for s in z.namelist() if regex.match(s)]
            if not arc_members:
                raise Exception(f"no members with {arcname = } in archive")

            z.extractall(path=tempdir_name, members=arc_members)

        w = os.walk(root)
        print('drives:', next(w)[1])
        for datadir, dirs, files in w:
            dest = datadir[len(root):]
            if len(dest) == 1:
                drive = dest.upper() + ':/'
                continue
                
            # attach driveletter to dest[ination]:
            _, rp = dest.split(os.sep, maxsplit=1)
            dest = drive + rp
            # make sure the dest[ination] exists..
            print('entering', dest)
            os.makedirs(dest, exist_ok=True)
            for file in files:
                src = datadir + os.sep + file
                # ..and move all files there:
                try:
                    # (a format-string w/ side-effect?! what could go wrong?)
                    print(f'{ shutil.move(src, dest) = }')
                except shutil.Error as e:
                    print(e)

