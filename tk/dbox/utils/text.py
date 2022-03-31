import itertools as it
import typing as ty

import re
import os
import urllib
import logging

L = logging.getLogger(__name__)

_RE_ONLY_WORDS = re.compile(r'[\W_]+')

# TODO move to a proper res/ dir? cf: https://gist.github.com/gruber/8891611
# NB, this regex matches most URLs but also apparently hangs in some cases.
# Also cf. https://github.com/Traumatizn/RegEx/blob/main/Python/Url_Pattern.md
# which is a copy of the original gist
_RE_URL = re.compile(r'''
  (?i)\b((?:https?:(?:/{1,3}|[a-z0-9%])|[a-z0-9.\-]+[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)/)(?:[^\s()<>{}\[\]]+|\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\))+(?:\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’])|(?:(?<!@)[a-z0-9]+(?:[.\-][a-z0-9]+)*[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)\b/?(?!@)))
'''.strip())


def is_url(s: str) -> bool:
  return _RE_URL.match(s)


def clean_camelcase_fname(fname: str) -> str:
  """Clean fname, e.g. `xyz___test123.abc.pdf` -> `XyzTest123Abc.pdf`"""
  def _clean_camelcase(s: str) -> str:
    s = _RE_ONLY_WORDS.sub(' ', urllib.parse.unquote_plus(s))
    return ''.join(map(str.capitalize, s.split()))
  fname, ext = os.path.splitext(fname)
  return _clean_camelcase(fname) + ext


def potential_pdf_names(url: str) -> ty.Iterable[str]:
  """A set of heuristics to infer potential pdf name from a URL path.

  The return values are sorted by "likelihood" of it being a pdf name, for some
  very ad-hoc notion of likelihood.
  """
  def _heuristics(url: urllib.parse.ParseResult, ext: str) -> ty.Iterable[str]:
    if url.path.endswith(ext): # a/b/c.pdf -> c.pdf
      yield os.path.basename(url.path.rstrip('/'))

    query_params = urllib.parse.parse_qs(url.query)
    if 'filename' in query_params:
      filename, *rest = query_params.pop('filename')
      if rest: L.warning('Ignoring multiple filenames: %s', rest)
      if filename.endswith(ext): yield filename

    for k, vs in query_params.items():
      yield from filter(lambda s: s.endswith(ext), vs)

  url_parsed = urllib.parse.urlparse(url)
  maybe_names = (_heuristics(url_parsed, e) for e in ('.pdf', '.epub'))
  clean_names = lambda names: map(clean_camelcase_fname, names)
  yield from it.chain(*map(clean_names, maybe_names))


def name_from(url: str) -> str:
  """Return the most likely name for the PDF."""
  return next(potential_pdf_names(url))

