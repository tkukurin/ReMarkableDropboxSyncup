import re
import os
import dataclasses as dcls
import typing as ty

from html.parser import HTMLParser

from tk.dbox.utils import types
from tk.dbox.utils import text as txtutil


PDF_BASE = 'https://arxiv.com/pdf/{id}.pdf'
ABS_BASE = 'https://arxiv.com/abs/{id}'


class ArxivExtractor(HTMLParser):

  @dcls.dataclass
  class Response(types.WithMetaResponse):
    arxiv_id: str
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


def meta_from_arxiv(html: str) -> ArxivExtractor.Response:
  extractor = ArxivExtractor()
  extractor.feed(html)
  return ArxivExtractor.Response.fromdict(extractor.description)


def absurl(id_or_url: str) -> str:
  id = os.path.basename(id_or_url).removesuffix('.pdf')
  return ABS_BASE.format(id=id)


def pdfurl(id_or_url: str) -> str:
  id = os.path.basename(id_or_url).removesuffix('.pdf')
  return PDF_BASE.format(id=id)


def maybe_id(s: str) -> bool:  # TODO improve+test this
  return re.search(r'^\d{4}\.\d{5}$', s.removesuffix('.pdf').strip('[]'))


def go(getter: ty.Callable[[str], str], id_or_url: str):
  url = absurl(id_or_url)
  page = getter(url)
  meta = meta_from_arxiv(page)
  name = txtutil.clean_camelcase(meta.title)
  name = f'{meta.arxiv_id}_{name}.pdf'
  return name, pdfurl(meta.arxiv_id)

