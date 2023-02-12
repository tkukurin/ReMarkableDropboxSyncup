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
  for method_name, method in methods.items():
    mparser = subparser.add_parser(
        method_name, parents=[common_args], help=I.getdoc(method))
    sig = I.signature(method)

    def add_type_param(flag, annot, default):
      """Really untested but seems to work."""
      kws = {}
      type_ = annot
      if ty.get_origin(annot) is ty.List:
        kws = {
          "action": "append",
          "nargs": "*",
        }
      # Optional type
      if ty.get_origin(annot) is ty.Union and type(None) in ty.get_args(annot):
        for arg in ty.get_args(annot):
          if arg is not type(None):
            type_ = arg
            break

      mparser.add_argument(flag, type=type_, default=default, **kws)

    for name, param in sig.parameters.items():
      if name == 'self': continue
      type_ = param.annotation if param.annotation != I._empty else str
      # if parameter has a default, then we don't see it as a raw CLI value.
      flag = f'--{name}' if param.default != I._empty else name
      add_type_param(flag, type_, param.default)

  args = parser.parse_args().__dict__
  cmd = args.pop('cmd')
  method = methods[cmd]

  def logged_method(*a, **kw):
    log.debug('Starting %s: %s', cmd, kw)
    result = method(*a, **kw)
    log.debug('Done')
    return result

  return (logged_method if log else method), args

