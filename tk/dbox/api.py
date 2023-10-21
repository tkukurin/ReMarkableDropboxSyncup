"""API wrappers.

Dumb idea since Dropbox has a Python API but I wanted to roll out sth simple
since the project needs only a small subset of its features.
"""
import dataclasses as dcls
import io
import json
import logging
import requests
import typing as ty

import base64

from datetime import datetime as dt
from tk.dbox.utils.type import WithMetaResponse

L = logging.getLogger(__name__)
T = ty.TypeVar('T')


def _pathnorm(path: ty.Optional[str]) -> str:
  """Dropbox: path cannot be `/`, otherwise needs a leading slash."""
  path = (path or '').lstrip('/')
  return ('/' + path) if path else ''


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




import http.server
import socketserver
import webbrowser
import urllib.parse as urlparse
from urllib.parse import parse_qs
import threading


class Api:

  ResponseType = ty.Type[requests.Response | dict | str]

  def __init__(self, base: str, auth: dict):
    """Format `base` s.t. `{}` is where the modifiable part of the API comes."""
    self.base = base
    self.auth_headers = {}
    self.auth = None
    if (u := auth.get('username')) and (p := auth.get('password')):
        self.auth = requests.auth.HTTPBasicAuth(u, p)
    else:
        self.auth_headers = auth

  def url(self, *path: str):
    return self.base.format('/'.join(path))

  @staticmethod
  def _response_matcher(T: ResponseType) -> ty.Callable[[requests.Response], T]:
    return ({
      str: lambda r: r.content.decode('utf8'),
      dict: lambda r: r.json(),
      requests.Response: lambda r: r
    })[T]

  def get(self, *path: str, T: ResponseType = dict) -> T:
    url = self.url(*path)
    response = requests.get(url, headers=self.auth_headers, auth=self.auth)
    if not response.ok:
      L.error('Failed: %s', response.status_code)
      raise Exception(response.text)
    return self._response_matcher(T)(response)

  def post(self, *path: str, json=None, headers=None, T: ResponseType = dict) -> T:
    url = self.url(*path)
    headers = {**self.auth_headers, **(headers or {})}
    response = requests.post(url, json=json, headers=headers, auth=self.auth)
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
        **self.auth_headers,
        'Content-Type': 'application/octet-stream',
        'Dropbox-API-Arg': json.dumps({
          'path': _pathnorm(path),
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


class Notion(Api):
  # https://developers.notion.com/docs/working-with-page-content

  def __init__(self, secret: str, pageid: str):
    self.secret = secret
    # NB, actually we should expect it to be a DB id.
    self.pageid = pageid
    super().__init__("https://api.notion.com/v1/{}", {
      "Authorization": f"Bearer {secret}",
      # Not sure whether ok to hardcode this ...
      "Notion-Version": "2022-06-28",
    })

  def add_paper(self, title: str, url: str, abstract: str, content: str = ""):
    title = title.replace('\n', ' ').strip()
    abstract = abstract.replace('\n', ' ').strip()
    content = content.replace('\n', ' ').strip()
    response = self.post("pages", json={
    #response = self.post("pages", json={
      "parent": { "database_id": self.pageid },
      # https://developers.notion.com/reference/block
      "children": [
        {
          "object": "block",
          "type": "paragraph",
          # https://developers.notion.com/reference/block#block-type-objects
          "paragraph": {
            "rich_text": [
              {
                "type": "text",
                "text": {
                  'content': abstract,
                  "link": None
                }
              }
            ],
            "color": "default"
          }
        },
      ],

      "properties": {
        'Name': {
          #'id': 'title',
          'type': 'title',
          'title': [{'type': 'text',
            'text': {
              'content': title,
              'link': None
            },
            'annotations': {'bold': False,
              'italic': False,
              'strikethrough': False,
              'underline': False,
              'code': False,
              'color': 'default'},
            'href': None}]
        },
        'Summary': {
          'type': 'rich_text',
          'rich_text': [{'type': 'text',
            'text': {
              "content": f'[ReMarkable] {content}',
              'link': None
            },
            'annotations': {'bold': False,
              'italic': False,
              'strikethrough': False,
              'underline': False,
              'code': False,
              'color': 'default'},
            'href': None}],
        },
        'Source': {
          'type': 'url',
          'url': url,
        },
      }
    })
    return response

  def get_page(self, is_db: bool = True):
    prefix = "databases" if is_db else "pages"
    response = self.get(prefix, page_id,)
    return response

  def get_blocks(self):
    response = self.get("blocks", page_id)
    return response


class Dropbox(Api):

  @staticmethod
  def auth_header(key: str, secret: str) -> dict:
    key = base64.b64encode(f'{key}:{secret}'.encode('utf8'))
    return dict(Authorization=f'Bearer {key}')

  def auth(self, client_id: str, client_secret: str, **kwargs) -> str:
    """Some hacky way to get authorization via local oauth2 flow.

    TODO integrate refresh tokens et al.
    """
    if kwargs:
      L.warning("Unexpected: %s", kwargs)
    authorization_endpoint = "https://www.dropbox.com/oauth2/authorize"
    redirect_uri = 'http://localhost:8000'
    code = None

    class Handler(http.server.SimpleHTTPRequestHandler):

      def do_GET(self):
        self.send_response(200)
        self.end_headers()

        query_components = parse_qs(urlparse.urlparse(self.path).query)
        if local_code := query_components.get('code'):
          nonlocal code
          code = local_code[0]
          self.wfile.write(bytes(f'Access Token: {code}', 'utf-8'))
          return

        # NB, if you don't set redirect_uri the user can manually c/p the token.
        # Set redirect_uri in https://www.dropbox.com/developers/apps/
        # "{authorization_endpoint}?client_id={client_id}&response_type=token&redirect_uri={redirect_uri}";
        # response_type can be token or code
        self.wfile.write(bytes(f'''
        <html>
          <script>
            window.location.href =
            "{authorization_endpoint}?token_access_type=offline&client_id={client_id}&response_type=code&redirect_uri={redirect_uri}";
          </script>
        </html>
        ''', 'utf-8'))

    webbrowser.open('http://localhost:8000')
    httpd = socketserver.TCPServer(('localhost', 8000), Handler)
    while code is None:  # note the ugly hack, not even sure it'll always work
      httpd.handle_request()

    token_url = 'https://api.dropbox.com/oauth2/token'
    response = requests.post(token_url, data={
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret,
    })
    json = response.json()

    # other outputs:
    # access_token String The access token to be used to call the Dropbox API.
    # expires_in Integer The length of time in seconds that the access token will be valid for.
    # token_type String Will always be bearer.
    # scope String The permission set applied to the token.
    # account_id String An API v2 account ID if this OAuth 2 flow is user-linked.
    # team_id String An API v2 team ID if this OAuth 2 flow is team-linked.
    # refresh_token String If the token_access_type was set to offline when
    # calling /oauth2/authorize, then response will include a refresh token.
    # This refresh token is long-lived and won't expire automatically. It can be
    # stored and re-used multiple times.
    # id_token String If the request includes OIDC scopes and is completed in
    # the response_type=code flow, then the payload will include an id_token
    # which is a JWT token.
    # uid String The API v1 identifier value. It is deprecated and should no
    # longer be used.
    return json["access_token"]

  def __init__(self, auth_headers: ty.Union[str, dict, tuple]):
    if isinstance(auth_headers, str):
      auth_headers = {'Authorization': f'Bearer {auth_headers}'}
    else:
      tok = self.auth(**auth_headers)
      auth_headers = {'Authorization': f'Bearer {tok}'}
    super().__init__('https://api.dropboxapi.com/2/{}', auth_headers)

  def _exhaust(
      self,
      data: GenericResponse,
      wrapper: ty.Callable,
      *path: str) -> GenericResponse:
    """Calls the continue endpoint until done. TODO make this not hacky."""
    while data.meta.get('has_more') and (cursor := data.meta.get('cursor')):
      data_next = wrapper(self.post)(*path, json={"cursor": cursor})
      data.content.extend(data_next.content)
      data = GenericResponse(content=data.content, meta=data_next.meta)
    return data

  def ls(self, path: str, recursive: bool = False, exhaust: bool = False):
    wrapper = wrap('entries')
    basepath = 'files', 'list_folder'
    data = wrapper(self.post)(*basepath, json={
      'path': _pathnorm(path),
      'recursive': recursive,
      'include_media_info': False,
      'include_deleted': False,
      'include_has_explicit_shared_members': False,
      'include_mounted_folders': True,
      'include_non_downloadable_files': True
    })
    return self._exhaust(data, wrapper, *basepath, 'continue') if exhaust else data

  def search(self, query: str, path: ty.Optional[str] = None,
      filename_only: bool = True,
      file_extensions: ty.Optional[list] = None,
      exhaust: bool = False):
    wrapper = wrap('matches')
    data = wrapper(self.post)('files', 'search_v2', json={
      'query': query,
      'options': {
          'path': _pathnorm(path),
          'max_results': 100,
          'file_status': 'active',
          'filename_only': filename_only,
          'file_extensions': file_extensions,
      },
      'match_field_options': {'include_highlights': False}
    })
    return self._exhaust(data, wrapper, 'files', 'search', 'continue_v2') if exhaust else data

  @wrap('metadata')
  def mv(self, src: str, dst: str, rename: bool = True):
    return self.post('files', 'move_v2', json={
      'from_path': _pathnorm(src),
      'to_path': _pathnorm(dst),
      'autorename': rename,  # Fail or not if destination exists.
      'allow_ownership_transfer': False
    })

  @wrap('metadata')
  def mkdir(self, dirpath: str):
    return self.post('files', 'create_folder_v2', json={
      'path': _pathnorm(dirpath),
      'autorename': False,  # don't let the server try to resolve naming conflicts
    })

  @wrap('metadata')
  def rm(self, path: str):
    return self.post('files', 'delete_v2', json={'path': _pathnorm(path)})

  @wrap('metadata')
  def ln(self, src: str, dst: str):
    '''Create symlink on Dropbox.'''
    ref = self.post(
      'files', 'copy_reference', 'get', json={'path': _pathnorm(src)})
    return self.post('files', 'copy_reference', 'save', json={
      'copy_reference': ref['copy_reference'],
      'path': _pathnorm(dst)
    })

  @wrap()
  def save_url(self, url: str, path: ty.Optional[str] = None):
    path = path or ('/' + url.rsplit('/')[1])
    return self.post('files', 'save_url', json={
      'url': url,
      'path': _pathnorm(path)
    })


class GenericHtml(Api):
  def __init__(self):
    super().__init__('{}', {})

  def get(self, *path: str):
    return super().get(*path, T=str)

