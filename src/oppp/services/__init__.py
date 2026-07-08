# Register services on import.
from oppp.services import pk as _pk  # noqa: F401
from oppp.services import rtb as _rtb  # noqa: F401
from oppp.services import safety as _safety  # noqa: F401
from oppp.services.base import FieldSpec, ServiceConfig, get_service, service_registry

__all__ = [
    "FieldSpec",
    "ServiceConfig",
    "get_service",
    "service_registry",
]
