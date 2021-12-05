import os
import typing as ty
import dataclasses as dcls

from tk.dbox.provider import arxiv
from tk.dbox.utils import text as txtutil


@dcls.dataclass
class Matcher:
  name: str
  match: ty.Callable[[str], bool]
  dispatch: ty.Callable[[str], ty.Any]


def getname(url: str):
  name, ext = os.path.splitext(os.path.basename(url))
  return txtutil.clean_camelcase(name) + ext

url_matchers = [
  Matcher('arxiv', lambda url: 'arxiv' in url, arxiv.go),
  Matcher('pdf', lambda url: url.endswith('.pdf'),
    lambda getter, url: (getname(url), url)),
]

nonurl_matchers = [
  Matcher('arxiv', arxiv.maybe_id, arxiv.go),
]


def dispatch(id_or_url: str):  # TODO -> ty.Optional[ty.Any]:
  if txtutil.is_url(id_or_url):
    for matcher in filter(lambda m: m.match(id_or_url), url_matchers):
      yield matcher.dispatch  # (id_or_url)
  else:
    for matcher in filter(lambda m: m.match(id_or_url), nonurl_matchers):
      yield matcher.dispatch  # (id_or_url)

