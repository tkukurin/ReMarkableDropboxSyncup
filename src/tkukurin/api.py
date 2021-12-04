'''API wrappers.

Dumb idea since Dropbox has a Python API but I wanted to roll out sth simple
since the project needs only a small subset of its features.
'''
from __future__ import annotations
import dataclasses as dcls
import io
import json
import logging
import requests
import typing as ty

import base64
import parse

from datetime import datetime as dt

L = logging.getLogger(__name__)
T = ty.TypeVar('T')


@dcls.dataclass
class WithMetaResponse:
  meta: dict = dcls.field(repr=False)

  @classmethod
  def fromdict(cls, d: dict):
    kws = {k: d.pop(k, None) for k in cls.__dataclass_fields__}
    kws['meta'] = d
    return cls(**kws)


@dcls.dataclass
class GenericResponse(ty.Generic[T], WithMetaResponse):
  content: T


@dcls.dataclass
class FileResponse(WithMetaResponse):
  id: str
  name: str
  path_display: ty.Optional[str]
  server_modified: ty.Optional[dt]
  content_hash: ty.Optional[str]

  @property
  def hash(self):
    return self.content_hash

  @property
  def path(self):
    return self.path_display

  @property
  def last_modified(self):
    return self.server_modified

  def __post_init__(self):
    if lm := self.server_modified:
      setattr(self, 'server_modified', dt.strptime(lm, '%Y-%m-%dT%H:%M:%SZ'))


class Api:

  ResponseType = ty.Literal[requests.Response, dict, str]
  def __init__(self, base: str, auth: dict):
    '''Format `base` s.t. `{}` is where the modifiable part of the API comes.'''
    self.base = base
    self.auth = auth

  def url(self, *path: str):
    return self.base.format('/'.join(path))

  def _response_matcher(
      self, T: ResponseType) -> ty.Callable[[requests.Response], T]:
    return ({
      str: lambda r: r.content.decode('utf8'),
      dict: lambda r: r.json(),
      requests.Response: lambda r: r
    })[T]

  def get(self, *path: str, T: ResponseType = dict) -> T:
    url = self.url(*path)
    response = requests.get(url, headers=self.auth)
    if not response.ok:
      L.error('Failed: %s', response.status_code)
      raise Exception(response.text)
    return self._response_matcher(T)(response)

  def post(self, *path: str, json=None, headers=None, T: ResponseType = dict) -> T:
    url = self.url(*path)
    response = requests.post(url, json=json, headers={**self.auth, **(headers or {})})
    if not response.ok:
      L.error('Failed: %s', response.status_code)
      raise Exception(response.text)
    return self._response_matcher(T)(response)


def _remap_out(content: ty.Any):
  '''Wraps Dropbox API response using some dumb heuristics.

  Files will be named and such.
  '''
  if isinstance(content, list):
    content = list(map(_remap_out, content))
  elif isinstance(content, dict):
    if 'id' in content:  # TODO: probably content.get('.tag') == 'file':
      return FileResponse.fromdict(content)
    elif (
        'metadata' in content and
        content.get('match_type', {}).get('.tag').startswith('filename')):
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
  def ls(self, path: str, recursive: bool = False):
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
  def search(self, query: str, path: ty.Optional[str] = None, filename_only=True):
    return self.post('files', 'search_v2', json={
      'query': query,
      'options': {
          'path': path or '',
          'max_results': 20,
          'file_status': 'active',
          'filename_only': filename_only
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

  @wrap()
  def save_url(self, url: str, path: ty.Optional[str] = None):
    path = path or ('/' + url.rsplit('/')[1])
    return self.post('files', 'save_url', json={
      'url': url,
      'path': path
    })


class Arxiv(Api):
  def __init__(self):
    super().__init__('https://arxiv.com/abs/{}', {})
    self.pdf_base = 'https://arxiv.com/pdf/{}.pdf'

  def url(self, path: str):
    return self.base.format(path.rsplit('/')[-1])

  def pdf_url(self, path: str):
    return self.pdf_base.format(path.rsplit('/')[-1])

  def get_meta(self, id_or_url: str):
    page = self.get(id_or_url, T=str)
    pdf_url = self.pdf_url(id_or_url)
    return {**parse.ArxivExtractor.get_description(page), 'pdf_url': pdf_url}

