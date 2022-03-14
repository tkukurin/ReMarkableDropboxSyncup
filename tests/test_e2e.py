"""E2e tests with a bit too much knowledge of the internal impl.
"""
import pytest
from unittest import mock
from types import SimpleNamespace as SN

from tk.dbox import api
from tk.dbox import main
from tk.dbox.provider import auto
from tk.dbox.utils import cli


@pytest.fixture
def cli_with_fakes() -> main.Cli:
  db = mock.Mock(spec_set=api.Dropbox)
  dbc = mock.Mock(spec_set=api.DropboxContent)
  cd = mock.Mock(spec_set=auto.Dispatcher)

  cli = main.Cli(db, dbc, cd)
  return cli


def test_dropboxLsMockedReturnsOneItem_cliLs_e2e(cli_with_fakes: main.Cli):
  cli_with_fakes.dropbox.ls.return_value = SN(content=[
    # just ensure the "necessary" fields are present to pass e2e tests
    SN(path='123', meta={'.tag': 'not_file'}),
  ])

  cli_with_fakes.ls('/mydir')

  cli_with_fakes.dropbox.ls.assert_called_once_with('/mydir')


def test_noExistingFiles_cliPut_e2e(cli_with_fakes: main.Cli):
  cli_with_fakes.content_dispatcher.return_value = iter([lambda *_: ('fname', 'url')])
  cli_with_fakes.dropbox.search.return_value = SN(content=[])

  cli_with_fakes.put('item', '/mydir')

  cli_with_fakes.dropbox.save_url.assert_called_once()

