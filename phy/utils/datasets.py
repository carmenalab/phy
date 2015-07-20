# -*- coding: utf-8 -*-

"""Utility functions for test datasets."""

#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

import hashlib
import os
import os.path as op

from .logging import info, warn
from .settings import _phy_user_dir, _ensure_dir_exists


#------------------------------------------------------------------------------
# Utility functions
#------------------------------------------------------------------------------

_BASE_URL = {
    'cortexlab': 'http://phy.cortexlab.net/data/samples/',
    'github': 'https://raw.githubusercontent.com/kwikteam/phy-data/master/',
    'local': 'http://localhost:8000/',
}


def _save_stream(r, path):
    with open(path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                f.flush()


def _download(url, stream=None):
    from requests import get
    r = get(url, stream=stream)
    if r.status_code != 200:
        warn("Error while downloading `{}`.".format(url))
        r.raise_for_status()
    return r


def download_text_file(url):
    """Download a text file."""
    return _download(url).text


def _md5(path, blocksize=2 ** 20):
    """Compute the checksum of a file."""
    m = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            buf = f.read(blocksize)
            if not buf:
                break
            m.update(buf)
    return m.hexdigest()


def _check_md5(path, checksum):
    if checksum is None:
        return
    return _md5(path) == checksum


def _check_md5_of_url(output_path, url):
    try:
        checksum = download_text_file(url + '.md5')
    except Exception:
        checksum = None
    finally:
        if checksum:
            if not _check_md5(output_path, checksum):
                raise RuntimeError("The checksum of the downloaded file "
                                   "doesn't match the provided checksum.")


def _validate_output_dir(output_dir):
    if output_dir is None:
        output_dir = '.'
    if not output_dir.endswith('/'):
        output_dir = output_dir + '/'
    output_dir = op.realpath(op.dirname(output_dir))
    if not op.exists(output_dir):
        os.mkdir(output_dir)
    return output_dir


def download_file(url, output_path=None):
    """Download a binary file from an URL.

    The checksum will be downloaded from `URL + .md5`. If this download
    succeeds, the file's MD5 will be compared to the expected checksum.

    Parameters
    ----------

    url : str
        The file's URL.
    output_path : str or None
        The path where the file is to be saved.

    Returns
    -------

    output_path : str
        The path where the file was downloaded.

    """
    if output_path is None:
        output_path = url.split('/')[-1]
    if op.exists(output_path):
        info("The file {} already exists: skipping.".format(output_path))
        return
    info("Downloading {0}...".format(url))
    r = _download(url, stream=True)
    _save_stream(r, output_path)
    _check_md5_of_url(output_path, url)
    return output_path


def download_test_data(name, phy_user_dir=None, force=False):
    """Download a test file."""
    phy_user_dir = phy_user_dir or _phy_user_dir()
    dir = op.join(phy_user_dir, 'test_data')
    _ensure_dir_exists(dir)
    path = op.join(dir, name)
    if not force and op.exists(path):
        return path
    url = _BASE_URL['github'] + 'test/' + name
    download_file(url, output_path=path)
    return path


def download_sample_data(filename, output_dir=None, base='cortexlab'):
    """Download a sample dataset.

    Parameters
    ----------

    filename : str
        Name of the sample dataset to download.
    output_dir : str
        The directory where to save the file.
    base : str
        The id of the base URL. Can be `'cortexlab'` or `'github'`.

    """
    output_dir = _validate_output_dir(output_dir)
    url = _BASE_URL[base] + filename
    output_path = op.join(output_dir, filename)
    try:
        download_file(url, output_path=output_path)
    except Exception as e:
        warn("An error occurred while downloading `{}` to `{}`: {}".format(
             url, output_path, str(e)))
