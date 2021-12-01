'''API wrappers.'''
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
    '''Base in format with `{}` where the replacement comes in.'''
    self.base = base
    self.auth = auth

  def url(self, *path: str):
    url = self.base.format('/'.join(path))
    L.info('Construct %s', url)
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


def _remap_out(content: ty.Any):
  if isinstance(content, list):
    content = list(map(_remap_out, content))
  elif isinstance(content, dict):
    if 'id' in content:
      path = content.pop('path_display', content['name'])
      return FileResponse(
        id=content.pop('id'),
        name=content.pop('name'),
        path=path,
        meta=content
      )
    elif (
        'metadata' in content and
        content.get('match_type', {}).get('.tag') == 'filename'):
      return _remap_out(content['metadata']['metadata'])
  return content


def _remap_in(arg: ty.Any):
  if isinstance(arg, FileResponse):
    arg = arg.path
  return arg


def wrap(main_key: str):
  def _wrap(f: ty.Callable):
    def _inner(*args, **kwargs):
      res = f(*map(_remap_in, args), **kwargs)
      content = _remap_out(res.pop(main_key))
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
      'autorename': False,
      'allow_ownership_transfer': False
    })

  @wrap('metadata')
  def ln(self, src: str, dst: str):
    ref = self.post('files', 'copy_reference', 'get', json={'path': src})
    return self.post('files', 'copy_reference', 'save', json={
      'copy_reference': ref['copy_reference'],
      'path': dst
    })

