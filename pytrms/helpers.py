import requests.exceptions

__all__ = [
    'PTRConnectionError',
    'setup_measurement_dir',
]


class PTRConnectionError(requests.exceptions.ConnectionError):
    pass


def setup_measurement_dir(config_dir=None, data_root_dir='D:/Data', suffix='',
        date_fmt = "%Y_%m_%d__%H_%M_%S"):
    """Create a new directory for saving the measurement and set it up.

    Optional: copy all files from the given config-directory.

    data_root_dir: the base folder for storing new measurement-directories
    suffix: will be appended to directory and data-file
    date_fmt: format for the source-folder and -file to be timestamped
    """
    import os
    import glob
    import shutil
    from collections import namedtuple
    from datetime import datetime
    from itertools import chain

    recipe = namedtuple('recipe', ['dirname', 'h5_file', 'pt_file', 'alarms_file'])
    _pt_formats = ['*.ionipt']
    _al_formats = ['*.alm']
    # make directory with current timestamp:
    now = datetime.now()
    new_h5_file = os.path.abspath(os.path.join(
        data_root_dir,
        now.strftime(date_fmt) + suffix,
        now.strftime(date_fmt) + suffix + '.h5',
    ))
    new_recipe_dir = os.path.dirname(new_h5_file)
    os.makedirs(new_recipe_dir, exist_ok=False)  # may throw!
    if not config_dir:
        # we're done here..
        return recipe(new_recipe_dir, new_h5_file, '', '')

    # find the *first* matching file or an empty string if no match...
    new_pt_file = next(chain.from_iterable(glob.iglob(config_dir + "/" + g) for g in _pt_formats), '')
    new_al_file = next(chain.from_iterable(glob.iglob(config_dir + "/" + g) for g in _al_formats), '')
    # ...and copy all files from the master-recipe-dir:
    files2copy = glob.glob(config_dir + "/*")
    for file in files2copy:
        new_file = shutil.copy(file, new_recipe_dir)
        try:  # remove write permission (a.k.a. make files read-only)
            mode = os.stat(file).st_mode
            os.chmod(new_file, mode & ~stat.S_IWRITE)
        except Exception as exc:
            # well, we can't set write permission
            pass

    return recipe(new_recipe_dir, new_h5_file, new_pt_file, new_al_file)

