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
import inspect as I
import json
import logging
import os
import sys

import api

from pathlib import Path


L = logging.getLogger(__name__)
PAPERS_DIR = '/books/papers'


def autoparse():
  common_args = argparse.ArgumentParser(add_help=False)
  common_args.add_argument('--verbose', action='store_true', default=False)
  common_args.add_argument('--keyfile', type=str, default='keys.json')
  parser = argparse.ArgumentParser()
  subparser = parser.add_subparsers(title='cmd', required=True, dest='cmd')
  methods = {
    name: obj for name, obj in I.getmembers(sys.modules[__name__])
    if I.isfunction(obj) and name != 'autoparse'
  }
  import pdb; pdb.set_trace()
  for mname, method in methods.items():
    mparser = subparser.add_parser(mname, parents=[common_args])
    sig = I.signature(method)
    param: I.Parameter
    for name, param in sig.parameters.items():
      if name == 'dropbox': continue  # TODO fix this
      type_ = param.annotation if param.annotation != I._empty else str
      default = param.default if param.default != I._empty else None
      mparser.add_argument(f'--{name}', type=type_, default=default)

  args = parser.parse_args().__dict__
  logging.basicConfig(level=logging.DEBUG if args.pop('verbose') else logging.INFO)

  with open(args.pop('keyfile')) as f:
    auth = json.load(f)['access_token']

  method = methods[args.pop('cmd')]
  method(api.Dropbox(auth), **args)


# TODO or maybe in a class?
# class Cli:

#   @classmethod
#   def parse(cls):
#     common_args = argparse.ArgumentParser(add_help=False)
#     common_args.add_argument('--verbose', action='store_true', default=False)
#     common_args.add_argument('--keyfile', type=str, default='keys.json')

#     parser = argparse.ArgumentParser()
#     subparser = parser.add_subparsers(title='cmd', required=True, dest='cmd')

#     methods = {m: d for m, d in I.getmembers(self) if I.ismethod(d)}
#     for mname, method in methods.values():
#       mparser = subparser.add_parser(mname, parents=[common_args])
#       sig = I.signature(method)
#       param: I.Parameter
#       for name, param in sig.parameters.items():
#         type_ = param.annotation if param.annotation != I._empty else str
#         default = param.default if param.default != I._empty else None
#         mparser.add_argument(f'--{name}', type=type_, default=default)

#     args = parser.parse_args()
#     logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

#     with open(args.keyfile) as f:
#       auth = json.load(f)['access_token']

#     cli = cls()
#     method = args.cmd


#     prog = f'{parser.prog} {args.cmd}'
#     if prog == parser_up.prog:
#       cli.upload(api.DropboxContent(auth), args.fname, args.remotedir)
#     elif prog == parser_sync.prog:
#       cli.sync(api.Dropbox(auth))
#     elif prog == parser_ls.prog:
#       print('\n'.join(
#         x.path for x in
#         api.Dropbox(auth).ls(args.remotedir).content
#         if x.meta['.tag'] != 'file'
#       ))

#   def __init__(self):
#     pass


def ls(dropbox: api.Dropbox, remotedir: str = PAPERS_DIR):
  print('\n'.join(
    x.path for x in
    dropbox.ls(remotedir).content
    # api.Dropbox(auth).ls(args.remotedir).content
    if x.meta['.tag'] != 'file'
  ))


def upload(dropbox: api.DropboxContent, fname: str, remotedir: str = PAPERS_DIR):
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
    # if file hashes are equal, don't do the move
    'hash': Accum(lambda f, o: f.hash == o.hash),
    # if the other file was modified after original, also don't move
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
  autoparse()
  #cli = Cli.parse()
  '''
  common_args = argparse.ArgumentParser(add_help=False)
  common_args.add_argument('--verbose', action='store_true', default=False)
  common_args.add_argument('--keyfile', type=str, default='keys.json')

  parser = argparse.ArgumentParser()
  subparser = parser.add_subparsers(title='cmd', required=True, dest='cmd')
  parser_sync = subparser.add_parser('sync', parents=[common_args])
  parser_up = subparser.add_parser('upload', parents=[common_args])
  parser_up.add_argument('--fname', type=str)
  parser_up.add_argument('--remotedir', type=str, default='/books/papers/')
  parser_ls = subparser.add_parser('ls', parents=[common_args])
  parser_ls.add_argument('--remotedir', type=str, default='/books/papers/')

  args = parser.parse_args()
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

  with open(args.keyfile) as f:
    auth = json.load(f)['access_token']

  # TODO automate argument parsing from Cli class
  # inspect arguments, auto set values, etc
  cli = Cli()

  prog = f'{parser.prog} {args.cmd}'
  if prog == parser_up.prog:
    cli.upload(api.DropboxContent(auth), args.fname, args.remotedir)
  elif prog == parser_sync.prog:
    cli.sync(api.Dropbox(auth))
  elif prog == parser_ls.prog:
    print('\n'.join(
      x.path for x in
      api.Dropbox(auth).ls(args.remotedir).content
      if x.meta['.tag'] != 'file'
    ))

  '''

