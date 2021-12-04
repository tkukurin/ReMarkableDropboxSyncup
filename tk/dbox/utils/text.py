import re

_RE_ONLY_WORDS = re.compile(r'[\W_]+')


def clean_camelcase(s: str) -> str:
  s = _RE_ONLY_WORDS.sub(' ', s)
  return ''.join(map(str.capitalize, s.split()))


