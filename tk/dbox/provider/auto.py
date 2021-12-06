import os
import typing as ty
import dataclasses as dcls
from collections import namedtuple

from tk.dbox import api
from tk.dbox.provider import arxiv
from tk.dbox.utils import text as txtutil


Uploadable = namedtuple('Uploadable', 'fname pdfurl')
UrlToUploadable = ty.Callable[[str], Uploadable]


@dcls.dataclass
class Matcher:
  name: str
  match: ty.Callable[[str], bool]
  dispatch: UrlToUploadable


class Dispatcher:
  def __init__(self):
    # TODO move this to constructor for injection?
    self.html = api.GenericHtml()
    _arxiv = lambda u: arxiv.go(self.html.get, u)
    self.url_matchers = [
      Matcher('arxiv', lambda u: 'arxiv' in u, _arxiv),
      Matcher('pdf', lambda u: u.endswith('.pdf'), lambda u: (txtutil.name_from(u), u)),
    ]
    self.nonurl_matchers = [
      Matcher('arxiv', arxiv.maybe_id, _arxiv),
      Matcher('local', lambda f: os.path.exists(f), lambda u: (os.path.basename(u), u)),
    ]

  def __call__(self, id_or_url: str) -> ty.Optional[UrlToUploadable]:
    if txtutil.is_url(id_or_url):
      for matcher in filter(lambda m: m.match(id_or_url), self.url_matchers):
        yield matcher.dispatch
    else:
      for matcher in filter(lambda m: m.match(id_or_url), self.nonurl_matchers):
        yield matcher.dispatch

