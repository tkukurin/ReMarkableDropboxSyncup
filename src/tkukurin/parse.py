import re
import typing as ty
from html.parser import HTMLParser


class ArxivExtractor(HTMLParser):
  def __init__(self):
    super().__init__()
    self.description = {}

  def handle_data(self, data: str):
    if self.get_starttag_text() == '<title>' and 'title' not in self.description:
      # ALT: there seems to be an rdf:Description in one of the comments
      # def handle_comment(self, data): if 'rdf:Description' in data: ...
      # Keep the title if something is buggy. EXPECT: `[12312.12312] Title`
      self.description['title'] = data
      if name_id_match := re.match(r'\[(\d+.\d+)\] (.*)', data):
        self.description['id'] = name_id_match[1]
        self.description['name'] = name_id_match[2]

  @classmethod
  def get_description(cls, html: str) -> ty.Optional[dict]:
    self = cls()
    self.feed(html)
    return self.description


