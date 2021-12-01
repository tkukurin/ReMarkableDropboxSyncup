import json
import logging

import api


logging.basicConfig(level=logging.INFO)
L = logging.getLogger(__name__)


def upload(dropbox: api.DropboxContent):
  with open('./test.txt', 'rb') as fp:
    dropbox.up(fp, '/test.txt')


def main(dropbox: api.Dropbox):
  base_contents = dropbox.ls('/')
  for file in base_contents.content:
    if file.name.endswith('.pdf'):
      other_same_name = dropbox.search(file)
      # dropbox.ln(file, '/books/test/tryagain.pdf')
      print(file)
      print(other_same_name.content)
      break


if __name__ == '__main__':
  with open('./keys.json') as f:
    auth = json.load(f)['access_token']

  dropboxup = api.DropboxContent(auth)
  dropbox = api.Dropbox(auth)

  main(dropbox)

