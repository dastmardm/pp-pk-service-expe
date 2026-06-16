"""Execute a machine query against the PharmaPendium search API and read the
result count. Used by the evaluation harness to compare against the gold `s`.

Uses stdlib urllib so the core has no extra HTTP dependency.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from oppp.models import MachineQuery
from oppp.services.base import ServiceConfig


@dataclass
class ExecutionResult:
    ok: bool
    count_total: int | None = None
    status: int | None = None
    error: str | None = None


def execute_count(
    machine_query: MachineQuery, service: ServiceConfig, *, timeout: float = 30.0
) -> ExecutionResult:
    """POST the query and return data.countTotal (None if unavailable)."""
    payload = machine_query.to_payload()
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        service.search_url,
        data=data,
        headers={"accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            count = body.get("data", {}).get("countTotal")
            return ExecutionResult(ok=True, count_total=count, status=resp.status)
    except urllib.error.HTTPError as e:
        return ExecutionResult(ok=False, status=e.code, error=f"HTTP {e.code}: {e.reason}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return ExecutionResult(ok=False, error=str(e))
    except (ValueError, KeyError) as e:
        return ExecutionResult(ok=False, error=f"bad response: {e}")
