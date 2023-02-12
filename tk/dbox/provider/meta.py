"""Methods for metadata retrieval for some paper URL.
"""
import re
import os
import urllib
import dataclasses as dcls
import logging
import typing as ty

from html.parser import HTMLParser

from tk.dbox.utils import type as types
from tk.dbox.utils import text as txtutil

L = logging.getLogger(__name__)


class CitationMetaExtractor(HTMLParser):

  @dcls.dataclass
  class Response(types.WithMetaResponse):
    paper_id: str
    title: str

  PREFIX_CITE = 'citation_'

  def __init__(self):
    super().__init__()
    self.description = {}

  def handle_starttag(self, tag: str, attrs: ty.List[ty.Tuple[str, str]]):
    if tag != 'meta': return
    attrs = dict(attrs)
    if (k := attrs.get('name', '')).startswith(self.PREFIX_CITE):
      k = k[len(self.PREFIX_CITE):]
      # Repeating meta tags get represented as lists, others normal strings.
      if v := self.description.get(k):
        if not isinstance(v, list): self.description[k] = [v]
        self.description[k].append(attrs['content'])
      else:
        self.description[k] = attrs['content']


@dcls.dataclass
class WithHtmlFetcher:
  """Fetches some metadata from HTML and returns name + PDF url.

  Useful for sites hosting papers (OpenReview, ArXiv).
  """

  # method to retrieve raw HTML from URL
  html_getter: ty.Callable[[str], str]
  # URLs with {id} in place of paper ID
  # e.g. pdfurl='https://arxiv.com/pdf/{id}.pdf'
  #      absurl = 'https://arxiv.com/abs/{id}'
  pdfurl: str
  absurl: str

  def __call__(self, id_or_url: str):
    id = self._get_id(id_or_url)
    url = self.mk_absurl(id)
    page = self.html_getter(url)
    meta = self._get_meta(page)
    name = txtutil.clean_camelcase_fname(meta.title)
    if meta.paper_id != id:
      L.warning("Differing IDs found: %s != %s", meta.paper_id, id)
      L.warning("(this will actually happen for e.g. OpenReview, WAI)")
    name = f'{id}_{name}.pdf'
    return name, self.mk_pdfurl(id)

  def _get_id(self, id_or_url: str):
    url = urllib.parse.urlparse(id_or_url)
    likely_url = (
      url.netloc.startswith('www.')
      # TODO check what python has instead of this quick and dirty heuristic
      or any(url.netloc.endswith(x) for x in ('.org', '.net', '.com'))
      or url.scheme
    )

    if not likely_url:  # assume ID given directly
      return url.geturl().removesuffix(".pdf")

    # TODO good enough for openreview and arxiv, but could be made nicer.
    # make sure to keep ordering since openreivew has `/pdf?id=` path
    query_params: dict[str, list] = urllib.parse.parse_qs(url.query)
    if attempt := query_params.get('id', [None])[0]:
      return attempt
    elif attempt := os.path.basename(url.path).removesuffix('.pdf'):
      return attempt

    L.warning("None of the heuristics matched, returning raw netloc: %s", url)
    return url.netloc

  def _get_meta(self, html: str) -> CitationMetaExtractor.Response:
    extractor = CitationMetaExtractor()
    extractor.feed(html)
    return CitationMetaExtractor.Response.fromdict(extractor.description)

  def mk_absurl(self, id: str) -> str:
    return self.absurl.format(id=id)

  def mk_pdfurl(self, id: str) -> str:
    return self.pdfurl.format(id=id)


def maybe_id(s: str) -> bool:  # TODO improve+test this
  return re.search(r'^\d{4}\.\d{5}$', s.removesuffix('.pdf').strip('[]'))

