import pytest
from tk.dbox.utils import text

@pytest.mark.parametrize('input_str', [
  'Ok Computer CAMEL-CASE',
  'ok_computer---camel//case',
  'ok    computer   camel \t\n case',
  'ok%20computer%20cAmEl_case',
])
def test_inputStr_cleanCamelcase_cleansCamelcase(input_str):
  assert text.clean_camelcase(input_str) == 'OkComputerCamelCase'

