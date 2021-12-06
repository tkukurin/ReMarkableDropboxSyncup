import typing as ty
import dataclasses as dcls

from tk.dbox import api
from tk.dbox.provider import arxiv
from tk.dbox.utils import text as txtutil


@dcls.dataclass
class Matcher:
  name: str
  match: ty.Callable[[str], bool]
  dispatch: ty.Callable[[str], ty.Any]


class Dispatcher:
  def __init__(self):
    # TODO move this to constructor for injection?
    self.html = api.GenericHtml()
    _arxiv = lambda u: arxiv.go(self.html.get, u)
    self.url_matchers = [
      Matcher('arxiv', lambda url: 'arxiv' in url, _arxiv),
      Matcher('pdf', lambda url: url.endswith('.pdf'),
        lambda url: (txtutil.name_from(url), url)),
    ]
    self.nonurl_matchers = [
      Matcher('arxiv', arxiv.maybe_id, _arxiv),
    ]

  def __call__(self, id_or_url: str):  # TODO -> ty.Optional[ty.Any]:
    if txtutil.is_url(id_or_url):
      for matcher in filter(lambda m: m.match(id_or_url), self.url_matchers):
        yield matcher.dispatch
    else:
      for matcher in filter(lambda m: m.match(id_or_url), self.nonurl_matchers):
        yield matcher.dispatch

