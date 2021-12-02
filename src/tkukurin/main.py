'''CLI app fixing ReMarkable sync annoyances for Dropbox to some extent.

Not yet sure what the intended interface is for this.
For now in `sync`, the assumptions are that:
  * ReMarkable uploads to the root folder
  * There is a subfolder called /books/ where you originally put your files
  * You want to symlink from the /books/ folder to the root file
  * You want to move your existing file to /books/archive
    * This is just to make it safe from accidental deletion
      (e.g. for whatever reason symlink fails, you can manually restore)

CLI reads credentials from local 'key.json' (`{"access_token": "..."}`).
'''
import argparse
import dataclasses as dcls
import inspect as I
import json
import logging
import os

import api

from pathlib import Path


logging.basicConfig(level=logging.INFO)
L = logging.getLogger(__name__)


class Defaults:
  PAPERS_DIR = '/books'
  ARCHIVE_DIR = '/books/archive'


def _init_cli_from_methods(cls, common_args: argparse.ArgumentParser) -> tuple:
  '''Automatically infer CLI from a method's public interface.'''
  parser = argparse.ArgumentParser()
  subparser = parser.add_subparsers(title='cmd', required=True, dest='cmd')
  isclassmethod = lambda x: I.ismethod(x) and x.__self__ != cls
  methods = {
    name: obj for name, obj in I.getmembers(cls)
    if I.isfunction(obj) and not isclassmethod(obj) and not name.startswith('_')
  }
  for mname, method in methods.items():
    mparser = subparser.add_parser(mname, parents=[common_args])
    sig = I.signature(method)
    for name, param in sig.parameters.items():
      if name == 'self': continue
      type_ = param.annotation if param.annotation != I._empty else str
      default = param.default if param.default != I._empty else None
      mparser.add_argument(f'--{name}', type=type_, default=default)
  args = parser.parse_args().__dict__
  cmd = args.pop('cmd')
  method = methods[cmd]

  def logged_method(*a, **kw):
    L.debug('Starting %s: %s', cmd, kw)
    result = method(*a, **kw)
    L.debug('Done')
    return result

  return logged_method, args


@dcls.dataclass
class Cli:
  dropbox: api.Dropbox
  dropbox_content: api.DropboxContent

  @classmethod
  def run(cls):
    common_args = argparse.ArgumentParser(add_help=False)
    common_args.add_argument('-v', '--verbose', action='count', default=0)
    common_args.add_argument('--keyfile', type=str, default='keys.json')
    method, args = _init_cli_from_methods(cls, common_args)
    if verbose := args.pop('verbose'):
      _log = L if verbose == 1 else logging.getLogger('')
      _log.setLevel(logging.DEBUG)
    with open(args.pop('keyfile')) as f:
      auth = json.load(f)['access_token']
    self = cls(api.Dropbox(auth), api.DropboxContent(auth))
    return method(self, **args)

  def ls(self, dir: str = Defaults.PAPERS_DIR):
    print('\n'.join(
      x.path for x in
      self.dropbox.ls(dir).content
      if x.meta['.tag'] != 'file'
    ))

  def upload(self, fname: str, dir: str = Defaults.PAPERS_DIR):
    local = Path(fname).expanduser()
    remote = Path(dir) / local.name
    L.info('Uploading local `%s` to Dropbox `%s`', local, remote)
    with local.open('rb') as fp:
      self.dropbox_content.up(fp, str(remote))

  def sync(
      self,
      papersdir: str = Defaults.PAPERS_DIR,
      archivedir: str = Defaults.ARCHIVE_DIR):
    class Accum:
      def __init__(self, chk):
        self.chk = chk
        self.fails = set()

      def __call__(self, file: api.FileResponse, other: api.FileResponse):
        if self.chk(file, other):
          self.fails.add((file.path, other.path))
          return True
        return False

      def __repr__(self):
        return f'Accum({self.fails})'

    early_exit = {
      # if file hashes are equal, don't do the move
      'hash': Accum(lambda f, o: f.hash == o.hash),
      # if the other file was modified after original, also don't move
      'modtime': Accum(lambda f, o: f.last_modified < o.last_modified),
    }

    is_pdf = lambda f: f.name.endswith('.pdf')
    is_rm_sync_folder = lambda f: (
      f.path.startswith(papersdir) and not f.path.startswith(archivedir))

    for file in filter(is_pdf, self.dropbox.ls('/').content):
      others_same_name = self.dropbox.search(file.name).content
      if other := next(filter(is_rm_sync_folder, others_same_name), None):
        if any(c(file, other) for c in early_exit.values()):
          continue
        # rm would be a bit unsafe if it fails, so this is a simple workaround.
        # con: you'll have to periodically manual delete the trash folder
        archive_path_cur = os.path.join(archive_path, other.name)
        L.info('Linking:\n  `%s`\n    -> `%s`', other.path, file.path)
        L.info('Archive:\n  `%s`\n    -> `%s`', other.path, archive_path_cur)
        try:
          self.dropbox.mv(other, archive_path_cur)
          self.dropbox.ln(file, other.path)
          # NB, we can also insert rm for archive_path_cur here
        except Exception:
          L.exception('Failed: %s -> %s', other.path, file.path)

    for name, cond in early_exit.items():
      L.debug('skipped[%s]:\n%s\n', name, cond)


if __name__ == '__main__':
  Cli.run()

