'''API wrappers.

Dumb idea since Dropbox has a Python API but I wanted to roll out sth simple
since the project needs only a small subset of its features.
'''
from datetime import datetime as dt
import dataclasses as dcls
import io
import json
import logging
import requests
import typing as ty

import base64


L = logging.getLogger(__name__)


class Api:
  def __init__(self, base: str, auth: dict):
    '''Format `base` s.t. `{}` is where the modifiable part of the API comes.'''
    self.base = base
    self.auth = auth

  def url(self, *path: str):
    url = self.base.format('/'.join(path))
    L.debug('Construct %s', url)
    return url

  def get(self, *path: str):
    url = self.url(*path)
    response = requests.get(url, headers=self.auth)
    if not response.ok:
      L.error('Failed: %s', response.status_code)
      raise Exception(response.text)
    return response.json()

  def post(self, *path: str, json=None, headers=None):
    url = self.url(*path)
    response = requests.post(url, json=json, headers={**self.auth, **(headers or {})})
    if not response.ok:
      L.error('Failed: %s', response.status_code)
      raise Exception(response.text)
    return response.json()


T = ty.TypeVar('T')


@dcls.dataclass
class WithMetaResponse:
  meta: dict = dcls.field(repr=False)


@dcls.dataclass
class GenericResponse(ty.Generic[T], WithMetaResponse):
  content: T


@dcls.dataclass
class FileResponse(WithMetaResponse):
  id: str
  name: str
  path: ty.Optional[str]
  last_modified: ty.Optional[dt]
  hash: ty.Optional[str]


def _remap_out(content: ty.Any):
  '''Wraps Dropbox API response using some dumb heuristics.

  Files will be named and such.
  '''
  if isinstance(content, list):
    content = list(map(_remap_out, content))
  elif isinstance(content, dict):
    if 'id' in content:  # TODO: probably content.get('.tag') == 'file':
      path = content.pop('path_display', content['name'])
      last_mod = content.pop('server_modified', None)
      if last_mod: last_mod = dt.strptime(last_mod, '%Y-%m-%dT%H:%M:%SZ')
      return FileResponse(
        id=content.pop('id'),
        name=content.pop('name'),
        path=path,
        last_modified=last_mod,
        hash=content.pop('content_hash', None),
        meta=content
      )
    elif (
        'metadata' in content and
        content.get('match_type', {}).get('.tag') == 'filename'):
      return _remap_out(content['metadata']['metadata'])
  return content


def _remap_in(arg: ty.Any):
  '''(Un)wrapping input arguments automatically in a dumb manner.

  This way you can use responses from the Dropbox API as inputs.
  Probably should be implemented as interface or auto-wrapped in the future.
  '''
  if isinstance(arg, FileResponse):
    arg = arg.path
  return arg


def wrap(extract_key: ty.Optional[str] = None):
  '''Dumb method which remaps inputs/outputs to an API endpoint.'''
  extract = (lambda d: d.pop(extract_key)) if extract_key else (lambda d: d)
  def _wrap(f: ty.Callable):
    def _inner(*args, **kwargs):
      res = f(*map(_remap_in, args), **kwargs)
      content = _remap_out(extract(res))
      return GenericResponse(meta=res, content=content)
    return _inner
  return _wrap


FileLike = ty.Union[str, FileResponse]


class DropboxContent(Api):

  def __init__(self, auth_headers: ty.Union[str, dict]):
    if isinstance(auth_headers, str):
      auth_headers = {'Authorization': f'Bearer {auth_headers}'}
    super().__init__('https://content.dropboxapi.com/2/{}', auth_headers)

  def up(self, fp: io.BytesIO, path: str):
    url = self.url('files', 'upload')
    response = requests.post(
      url, data=fp.read(), headers={
        **self.auth,
        'Content-Type': 'application/octet-stream',
        'Dropbox-API-Arg': json.dumps({
          'path': path,
          'mode': 'add',
          'autorename': True,
          'mute': False,
          'strict_conflict': False
        })
      })
    if not response.ok:
      L.error('Failed: %s', response.status_code)
      raise Exception(response.text)
    return GenericResponse(meta={}, content=response.json())


class Dropbox(Api):

  @staticmethod
  def auth_header(key: str, secret: str) -> dict:
    key = base64.b64encode(f'{key}:{secret}'.encode('utf8'))
    return dict(Authorization=f'Bearer {key}')

  def __init__(self, auth_headers: ty.Union[str, dict]):
    if isinstance(auth_headers, str):
      auth_headers = {'Authorization': f'Bearer {auth_headers}'}
    super().__init__('https://api.dropboxapi.com/2/{}', auth_headers)

  @wrap('entries')
  def ls(self, path: FileLike, recursive: bool = False):
    if path == '/': path = ''  # root folder this way
    return self.post('files', 'list_folder', json={
      'path': path or '',
      'recursive': recursive,
      'include_media_info': False,
      'include_deleted': False,
      'include_has_explicit_shared_members': False,
      'include_mounted_folders': True,
      'include_non_downloadable_files': True
    })

  @wrap('matches')
  def search(self, query: str, path: ty.Optional[str] = None):
    return self.post('files', 'search_v2', json={
      'query': query,
      'options': {
          'path': path or '',
          'max_results': 20,
          'file_status': 'active',
          'filename_only': False
      },
      'match_field_options': {'include_highlights': False}
    })

  @wrap('metadata')
  def mv(self, src: str, dst: str):
    return self.post('files', 'move_v2', json={
      'from_path': src,
      'to_path': dst,
      'autorename': False,  # Fail if destination exists.
      'allow_ownership_transfer': False
    })

  @wrap('metadata')
  def rm(self, path: str):
    return self.post('files', 'delete_v2', json={'path': path})

  @wrap('metadata')
  def ln(self, src: str, dst: str):
    '''Create symlink on Dropbox.'''
    ref = self.post('files', 'copy_reference', 'get', json={'path': src})
    return self.post('files', 'copy_reference', 'save', json={
      'copy_reference': ref['copy_reference'],
      'path': dst
    })

