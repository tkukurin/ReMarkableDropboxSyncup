import pytest
from tk.dbox.utils import text

@pytest.mark.parametrize('input_str', [
  'Ok Computer CAMEL-CASE',
  'ok_computer---camel//case',
  'ok    computer   camel \t\n case',
  'ok%20computer%20cAmEl_case',
])
def test_inputStr_cleanCamelcase_cleansCamelcase(input_str: str):
  assert text.clean_camelcase(input_str) == 'OkComputerCamelCase'


@pytest.mark.parametrize('input_url', [
  'https://arxiv.org/pdf/2011.14522.pdf',
  'https://mywebsite.com/abc?filename=2011.14522.pdf',
  'https://someothersite/abc?abc=2011.14522.pdf',
])
def test_inputUrlSinglePdf_potentialNames_extractsOnePdfName(input_url: str):
  assert list(text.potential_pdf_names(input_url)) == ['201114522.pdf']
  assert text.name_from(input_url) == '201114522.pdf'


def test_inputUrlMultiplePdf_potentialNames_extractsAllPdfNamesByLikelihood():
  input_url = 'https://x.org/pdf/2011.14522.pdf?other=x.pdf&filename=mypdf.pdf'
  assert list(text.potential_pdf_names(input_url)) == [
    '201114522.pdf',
    'Mypdf.pdf',
    'X.pdf'
  ]

