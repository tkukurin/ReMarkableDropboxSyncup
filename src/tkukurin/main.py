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
import json
import logging
import os
import typing as ty

from .utils import cli, text as txtutil
from . import api
from . import arxiv

from pathlib import Path


logging.basicConfig(level=logging.INFO)
L = logging.getLogger(__name__)


class Defaults:
  BOOKS_DIR = '/books'
  PAPERS_DIR = '/books/papers'
  ARCHIVE_DIR = '/books/archive'


@dcls.dataclass
class Cli:
  dropbox: api.Dropbox
  dropbox_content: api.DropboxContent
  html: api.GenericHtml

  @classmethod
  def run(cls: ty.Type) -> ty.Any:
    common_args = argparse.ArgumentParser(add_help=False)
    common_args.add_argument('-v', '--verbose', action='count', default=0)
    common_args.add_argument('--keyfile', type=str, default='keys.json')
    method, args = cli.cli_from_instancemethods(cls, common_args, log=L)
    if verbose := args.pop('verbose'):
      _log = L if verbose == 1 else logging.getLogger('')
      _log.setLevel(logging.DEBUG)
    with open(args.pop('keyfile')) as f:
      auth = json.load(f)['access_token']
    self = cls(
        dropbox=api.Dropbox(auth),
        dropbox_content=api.DropboxContent(auth),
        html=api.GenericHtml())
    return method(self, **args)

  def ls(self, dir: str = Defaults.BOOKS_DIR):
    """List immediate contents of `dir`"""
    print('\n'.join(
      x.path for x in
      self.dropbox.ls(dir).content
      if x.meta['.tag'] != 'file'
    ))

  def arxiv(self, url: str, dir: str = Defaults.PAPERS_DIR):
    """Get file from arxiv (URL or ID) and send to dropbox `dir`.

    NB: hastily implemented; file will be renamed to `file (1)` if exists.
    """
    # https://www.dropbox.com/developers/documentation/http/documentation#files-save_url
    page = self.html.get(arxiv.absurl(url))
    meta = arxiv.meta_from_arxiv(page)
    name = txtutil.clean_camelcase(meta.title)
    path = os.path.join(dir, f'{meta.arxiv_id}_{name}.pdf')
    L.info('Pulling PDF: %s -> %s', arxiv.pdfurl(meta.arxiv_id), path)
    response = self.dropbox.save_url(arxiv.pdfurl(meta.arxiv_id), path)
    L.info('Job ID: %s', response.content.get('async_job_id'))

  def upload(self, fname: str, dir: str = Defaults.BOOKS_DIR):
    """Upload local `fname` to Dropbox `dir`."""
    local = Path(fname).expanduser()
    remote = Path(dir) / local.name
    L.info('Uploading local `%s` to Dropbox `%s`', local, remote)
    with local.open('rb') as fp:
      self.dropbox_content.up(fp, str(remote))

  def sync(
      self,
      syncdir: str = Defaults.BOOKS_DIR,
      archivedir: str = Defaults.ARCHIVE_DIR):
    """Sync files by making symlinks from Dropbox `syncdir` to root.

    This method assumes that Dropbox root contains annotated PDFs and the
    un-annotated PDFs are in `syncdir`. This is due to the way ReMarkable
    currently uploads files.
    """
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
      f.path.startswith(syncdir) and not f.path.startswith(archivedir))

    for file in filter(is_pdf, self.dropbox.ls('/').content):
      others_same_name = self.dropbox.search(
          file.name, path=syncdir, filename_only=True).content
      L.debug('Match %s: %s', file.name, [f.path for f in others_same_name])
      if other := next(filter(is_rm_sync_folder, others_same_name), None):
        if any(c(file, other) for c in early_exit.values()):
          continue
        # rm would be a bit unsafe if it fails, so this is a simple workaround.
        # con: you'll have to periodically manual delete the trash folder
        archive_path_cur = os.path.join(archivedir, other.name)
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

