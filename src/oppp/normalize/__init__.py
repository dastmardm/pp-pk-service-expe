from oppp.normalize.base import (
    NormalizationResult,
    Normalizer,
    get_normalizer,
    normalizer_registry,
)
from oppp.normalize.strategies import (
    ClosedSetNormalizer,
    ConservativeNormalizer,
    DrugNormalizer,
)

__all__ = [
    "NormalizationResult",
    "Normalizer",
    "get_normalizer",
    "normalizer_registry",
    "normalize",
    "ClosedSetNormalizer",
    "ConservativeNormalizer",
    "DrugNormalizer",
]


def normalize(
    fragment: str, field: str, bucket: str, context: object = None
) -> NormalizationResult:
    """Fixed-policy normalizer dispatch (CONST-8).

    Routes by field/bucket:
      * field=="drugs"  -> DrugNormalizer
      * bucket=="closed" -> ClosedSetNormalizer
      * otherwise       -> ConservativeNormalizer
    """
    if field == "drugs":
        return DrugNormalizer().normalize(fragment, field=field, bucket=bucket)
    if bucket == "closed":
        return ClosedSetNormalizer().normalize(fragment, field=field, bucket=bucket)
    return ConservativeNormalizer().normalize(fragment, field=field, bucket=bucket)
