'''CLI app with actions to sync remote directories or upload to Dropbox.

For `sync`, the assumptions are that:
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

from pathlib import Path


L = logging.getLogger(__name__)


def upload(dropbox: api.DropboxContent, fname: str, remote_path: str):
  local = Path(fname).expanduser()
  remote = Path(remote_path) / local.name
  L.info('Uploading local `%s` to Dropbox `%s`', local, remote)
  with local.open('rb') as fp:
    dropbox.up(fp, str(remote))


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
  common_args = argparse.ArgumentParser(add_help=False)
  common_args.add_argument('--verbose', action='store_true', default=False)
  common_args.add_argument('--keyfile', type=str, default='keys.json')

  parser = argparse.ArgumentParser()
  subparser = parser.add_subparsers(title='cmd', required=True, dest='cmd')
  parser_act = subparser.add_parser('sync', parents=[common_args])
  parser_up = subparser.add_parser('upload', parents=[common_args])
  parser_up.add_argument('--fname', type=str)
  parser_up.add_argument('--remotedir', type=str, default='/books/papers/')
  parser_folders = subparser.add_parser('ls', parents=[common_args])
  parser_folders.add_argument('--remotedir', type=str, default='/books/papers/')

  args = parser.parse_args()
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

  with open(args.keyfile) as f:
    auth = json.load(f)['access_token']

  if args.cmd == 'upload':
    upload(api.DropboxContent(auth), args.fname, args.remotedir)
  elif args.cmd == 'sync':
    sync(api.Dropbox(auth))
  elif args.cmd == 'ls':
    print('\n'.join(
      x.path for x in
      api.Dropbox(auth).ls(args.remotedir).content
      if x.meta['.tag'] != 'file'
    ))


