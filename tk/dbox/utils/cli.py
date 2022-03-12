import argparse
import typing as ty
import inspect as I
import logging


def prompt(prompt: str, accepted_responses: ty.Sequence[str]) -> str:
  """Prompt until case-insensitive matches from `accepted_responses` are chosen.

  Returns lowercased user answer. Last entry in `accepted_responses` is
  considered to be the default value (if user responds with empty string).
  """
  default = accepted_responses[-1].upper()
  responses_str = '/'.join([*accepted_responses[:-1], default])
  prompt = f'{prompt} ({responses_str}) > '
  while (response := (input(prompt) or default).lower()) not in accepted_responses:
    print('Please respond', responses_str.lower())
  return response


def cli_from_instancemethods(
    cls: ty.Type,
    common_args: argparse.ArgumentParser,
    log: logging.Logger) -> ty.Tuple[ty.Callable, dict]:
  '''Automatically infer CLI from a method's public interface.

  Returns a method to be called and corresponding args (incl `common_args`).
  '''
  parser = argparse.ArgumentParser()
  subparser = parser.add_subparsers(title='cmd', required=True, dest='cmd')
  isclassmethod = lambda x: I.ismethod(x) and x.__self__ != cls
  methods = {
    name: obj for name, obj in I.getmembers(cls)
    if I.isfunction(obj) and not isclassmethod(obj) and not name.startswith('_')
  }
  for mname, method in methods.items():
    mparser = subparser.add_parser(
        mname, parents=[common_args], help=I.getdoc(method))
    sig = I.signature(method)
    for name, param in sig.parameters.items():
      if name == 'self': continue
      type_ = param.annotation if param.annotation != I._empty else str
      flag = f'--{name}' if param.default != I._empty else name
      mparser.add_argument(flag, type=type_, default=param.default)
  args = parser.parse_args().__dict__
  cmd = args.pop('cmd')
  method = methods[cmd]

  def logged_method(*a, **kw):
    log.debug('Starting %s: %s', cmd, kw)
    result = method(*a, **kw)
    log.debug('Done')
    return result

  return (logged_method if log else method), args

