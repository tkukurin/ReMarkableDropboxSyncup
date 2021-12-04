import dataclasses as dcls


@dcls.dataclass
class WithMetaResponse:
  meta: dict = dcls.field(repr=False)

  @classmethod
  def fromdict(cls, d: dict):
    kws = {k: d.pop(k, None) for k in cls.__dataclass_fields__}
    kws['meta'] = d
    return cls(**kws)

