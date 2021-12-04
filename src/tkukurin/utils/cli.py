import argparse
import typing as ty
import inspect as I
import logging


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
      default = param.default if param.default != I._empty else None
      mparser.add_argument(f'--{name}', type=type_, default=default)
  args = parser.parse_args().__dict__
  cmd = args.pop('cmd')
  method = methods[cmd]

  def logged_method(*a, **kw):
    log.debug('Starting %s: %s', cmd, kw)
    result = method(*a, **kw)
    log.debug('Done')
    return result

  return (logged_method if log else method), args

