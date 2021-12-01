'''To-be CLI app, for now just calls sync with default options.

The assumptions are that:
  * ReMarkable uploads to the root folder
  * There is a subfolder called /books/ where you originally put your files
  * You want to symlink from the /books/ folder to the root file
  * You want to move your existing file to /books/archive
    * This is just to make it safe from accidental deletion
      (e.g. for whatever reason symlink fails, you can manually restore)

Reads credentials from local JSON file 'key.json' (`{"access_token": "..."}`).
'''
import argparse
import json
import logging
import os

import api


L = logging.getLogger(__name__)


def main():
  # TODO actually parse etc
  parser = argparse.ArgumentParser()
  sync = parser.add_argument_group('sync')
  upload = parser.add_argument_group('upload')
  return parser.parse_args()


def upload(dropbox: api.DropboxContent, fname: str, remote_path: str):
  # TODO make a bit more robust wrt. pathname resolution
  with open(fname, 'rb') as fp:
    dropbox.up(fp, f'{remote_path}/{fname}')


def sync(dropbox: api.Dropbox):

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
    'hash': Accum(lambda f, o: f.hash == o.hash),
    'modtime': Accum(lambda f, o: f.last_modified < o.last_modified),
  }

  is_pdf = lambda f: f.name.endswith('.pdf')
  archive_path = '/books/archive'
  is_rm_sync_folder = lambda f: (
    f.path.startswith('/books/') and not f.path.startswith(archive_path))

  for file in filter(is_pdf, dropbox.ls('/').content):
    others_same_name = dropbox.search(file.name).content
    if other := next(filter(is_rm_sync_folder, others_same_name), None):
      if any(c(file, other) for c in early_exit.values()):
        continue
      # rm would be a bit unsafe if it fails, so this is a simple workaround.
      # con: you'll have to periodically manual delete the trash folder
      archive_path = os.path.join(archive_path, other.name)
      L.info('Linking:\n  `%s`\n    -> `%s`', other.path, file.path)
      L.info('Archive:\n  `%s`\n    -> `%s`', other.path, archive_path)
      try:
        dropbox.mv(other, archive_path)
        dropbox.ln(file, other.path)
      except Exception:
        L.exception('Failed: %s -> %s', other.path, file.path)

  for name, cond in early_exit.items():
    L.debug('skipped[%s]:\n%s\n', name, cond)


if __name__ == '__main__':
  # TODO add verbose flag
  logging.basicConfig(level=logging.DEBUG)

  with open('./keys.json') as f:
    auth = json.load(f)['access_token']

  dx_content = api.DropboxContent(auth)
  dx = api.Dropbox(auth)
  sync(dx)

