import os
import itertools as it
import typing as ty
import dataclasses as dcls
import logging
from collections import namedtuple

from tk.dbox import api
from tk.dbox.provider import meta
from tk.dbox.utils import text as txtutil

L = logging.getLogger(__name__)

Uploadable = namedtuple('Uploadable', 'fname pdfurl')
UrlToUploadable = ty.Callable[[str], Uploadable]


@dcls.dataclass
class Matcher:
  name: str
  match: ty.Callable[[str], bool]
  dispatch: UrlToUploadable


class Dispatcher:
  def __init__(self):
    _get = api.GenericHtml().get
    self._arxiv = _arxiv = meta.WithHtmlFetcher(
      _get,
      pdfurl='https://arxiv.org/pdf/{id}.pdf',
      absurl='https://arxiv.org/abs/{id}',
    )
    self._review = _review = meta.WithHtmlFetcher(
      _get,
      pdfurl='https://openreview.net/pdf?id={id}',
      absurl='https://openreview.net/forum?id={id}',
    )
    self.url_matchers = [
      Matcher('arxiv', lambda u: any(x in u for x in ('arxiv', )), _arxiv),
      Matcher('openreview', lambda u: any(x in u for x in ('openreview', )), _review),
      Matcher('pdf', lambda u: u.endswith('.pdf'), lambda u: (txtutil.name_from(u), u)),
      Matcher('epub', lambda u: u.endswith('.epub'), lambda u: (txtutil.name_from(u), u)),
    ]
    self.nonurl_matchers = [
      Matcher('arxiv', meta.maybe_id, _arxiv),
      Matcher('local', lambda f: os.path.exists(f), lambda u: (os.path.basename(u), u)),
    ]

  def by_name(self, name: str) -> ty.Generator[ty.Optional[UrlToUploadable], None, None]:
    matchers = it.chain(self.url_matchers, self.nonurl_matchers)
    return (m.dispatch for m in matchers if m.name == name)

  def __call__(self, id_or_url: str) -> ty.Generator[ty.Optional[UrlToUploadable], None, None]:
    if txtutil.is_url(id_or_url):
      for matcher in filter(lambda m: m.match(id_or_url), self.url_matchers):
        L.debug("Matched: %s", matcher)
        yield matcher.dispatch
    else:
      for matcher in filter(lambda m: m.match(id_or_url), self.nonurl_matchers):
        L.debug("Matched: %s", matcher)
        yield matcher.dispatch

