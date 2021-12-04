import os
from src.tkukurin import parse


def test_sample_arxiv():
  with open(os.path.join(os.path.dirname(__file__), 'data/arxiv.html')) as f:
    description = parse.ArxivExtractor.get_description(f.read())

  assert description['id'] == '2106.09608'
  assert description['name'] == 'Learning Knowledge Graph-based World Models of Textual Environments'

