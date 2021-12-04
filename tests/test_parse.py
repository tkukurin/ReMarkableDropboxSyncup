import pytest
import os
from src.tkukurin import arxiv


def test_arxivPage_parse_extractsMetadata():
  with open(os.path.join(os.path.dirname(__file__), 'data/arxiv.html')) as f:
    description = arxiv.meta_from_arxiv(f.read())

  assert description.arxiv_id == '2106.09608'
  assert description.title == 'Learning Knowledge Graph-based World Models of Textual Environments'


@pytest.mark.parametrize('valid_input', [
  '123.123',
  'https://arxiv.com/abs/123.123',
  'https://arxiv.com/abs/123.123.pdf',
])
def test_validArxivInputs_geturl_returnsArxivUrl(valid_input):
  assert arxiv.absurl(valid_input) == 'https://arxiv.com/abs/123.123'
  assert arxiv.pdfurl(valid_input) == 'https://arxiv.com/pdf/123.123.pdf'

