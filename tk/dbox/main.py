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
import datetime as dt
import json
import logging
import os
import typing as ty

from tk.dbox import api
from tk.dbox.provider import auto
from tk.dbox.utils import cli

from pathlib import Path


logging.basicConfig(level=logging.INFO)
L = logging.getLogger(__name__)


class Defaults:
  BOOKS_DIR = '/books'
  PAPERS_DIR = '/books/papers'
  ARCHIVE_DIR = '/books/archive'

  CONFIG_JSON = Path('~/.tkapikeys.json').expanduser()


@dcls.dataclass
class Cli:
  dropbox: api.Dropbox
  dropbox_content: api.DropboxContent
  content_dispatcher: auto.Dispatcher

  @classmethod
  def run(cls: ty.Type) -> ty.Any:
    common_args = argparse.ArgumentParser(add_help=False)
    common_args.add_argument('-v', '--verbose', action='count', default=0)
    common_args.add_argument('--cfg', type=str, default=Defaults.CONFIG_JSON)
    method, args = cli.cli_from_instancemethods(cls, common_args, log=L)
    if verbose := args.pop('verbose'):
      _log = L if verbose == 1 else logging.getLogger('')
      _log.setLevel(logging.DEBUG)
    with open(args.pop('cfg')) as f:
      auth = json.load(f)['dropbox_access_token']
    self = cls(
        dropbox=api.Dropbox(auth),
        dropbox_content=api.DropboxContent(auth),
        content_dispatcher=auto.Dispatcher())
    return method(self, **args)

  def ls(self, dir: str = Defaults.BOOKS_DIR):
    """List immediate contents of `dir`"""
    print('\n'.join(
      x.path for x in
      self.dropbox.ls(dir).content
      if x.meta['.tag'] != 'file'
    ))

  def put(
      self,
      item: str,
      dir: str = Defaults.PAPERS_DIR,
      name: str = None,
      dispatcher: str = None):
    """Send given file to dropbox `dir`.

    The `item` parameter can be a local directory, pdf, or ArXiv ID.
    If `dispatcher` is set, the dispatcher will explicitly be chosen by name.
    If `name` is set, it will overwrite the default file name.
    """
    # https://www.dropbox.com/developers/documentation/http/documentation#files-save_url
    dispatcher = next(
      self.content_dispatcher(item) if dispatcher is None else
      self.content_dispatcher.by_name(dispatcher), None)

    if dispatcher is None:
      return L.error('Failed to find dispatcher for: %s', item)

    fname, pdfurl = dispatcher(item)
    if name:
      L.debug('Overwriting %s with %s', fname, name)
      fname = name
    path = os.path.join(dir, fname)

    # check for existing files, allow user to bail
    if existing := self.dropbox.search(fname, file_extensions=['pdf']).content:
      existing = [x.name for x in existing]
      if (response := cli.prompt(f'Found: {existing}. Continue?', 'yn')) == 'n':
        return L.info('Cancelling due to duplicate files: %s', existing)

    if dir in (Defaults.PAPERS_DIR,):
      cur = dt.datetime.now()
      new_name = os.path.join(dir, f"{cur.year}-{cur.month:02d}")
      path = os.path.join(new_name, fname)
      try:
        L.info("Trying to create %s...", new_name)
        result = self.dropbox.mkdir(new_name)
      except:
        L.info("Creating folder %s failed, probably exists", new_name)

    L.info('Transfering PDF: %s -> %s', pdfurl, path)
    # NB this is some code smell, make dispatch handle this transparently?
    # Maybe by returning a function reference
    if (local := Path(pdfurl).expanduser()).exists():
      remote = Path(dir) / fname
      L.info('Uploading local `%s` to Dropbox `%s`', local, remote)
      with local.open('rb') as fp:
        response = self.dropbox_content.up(fp, str(remote))
    else:
      response = self.dropbox.save_url(pdfurl, path)
      L.info('Job ID: %s', response.content.get('async_job_id'))
    return L.info('Server response: %s', response)

  def arxivfix(self):
    """Rename leftover ArXiv files (`1234.12345.pdf`) to contain titles."""
    from tk.dbox.provider import arxiv
    html = api.GenericHtml()
    L.info('Listing *all* files...')
    # Doesn't seem it supports regexes?
    pdfs = self.dropbox.search('pdf', file_extensions=['pdf'], exhaust=True)
    L.info('Found %s PDFs. Looking for files to rename.', len(pdfs.content))
    for file in pdfs.content:
      if arxiv.maybe_id(file.name):
        new_name, _ = arxiv.go(html.get, file.name)
        basepath, _ = os.path.split(file.path)
        new_path = os.path.join(basepath, new_name)
        L.info('Rename:\n  `%s`\n    -> `%s`', file.path, new_path)
        self.dropbox.mv(file.path, new_path)

  def sync(
      self,
      syncdir: str = Defaults.BOOKS_DIR,
      archivedir: str = Defaults.ARCHIVE_DIR):
    """Sync files by moving from root to `syncdir`.

    This method assumes that Dropbox root contains annotated PDFs and the
    un-annotated PDFs are somewhere in `syncdir`, e.g. if syncdir is `/books`.
      * /AttentionIsAllYouNeed.pdf
      * /books/nlp/AttentionIsAllYouNeed.pdf

    The old file will be moved to `archivedir` for just-in-case backup.
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
    L.info('Early exit conditions: %s', list(early_exit))

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
        try:
          L.info('Archive:\n  `%s`\n    -> `%s`', other.path, archive_path_cur)
          self.dropbox.mv(other, archive_path_cur)
          L.info('Moving:\n  `%s`\n    -> `%s`', file.path, other.path)
          self.dropbox.mv(file, other.path)
          # NB, we can also insert rm for archive_path_cur here
        except Exception:
          L.exception('Failed: %s -> %s', other.path, file.path)

    for name, cond in early_exit.items():
      L.debug('skipped[%s]:\n%s\n', name, cond)

  def s(self, what: str, ext: str = '') -> None:
    """Search dropbox for files with extension `ext` (comma-separated).

    Example:
      tkdbox s "my file" --ext pdf,epub
    """
    found = self.dropbox.search(
        what,
        file_extensions=ext.split(',') if ext else None,
        filename_only=True
    ).content
    print('\n'.join([ f.path for f in found ]))


if __name__ == '__main__':
  Cli.run()

