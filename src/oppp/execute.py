"""Execute a machine query against the PharmaPendium search API.

Uses stdlib urllib so the core has no extra HTTP dependency (NFR-004).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from oppp.models import ExecutionResult, MachineQuery, RowExecutionResult
from oppp.services.base import ServiceConfig


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


def execute_rows(
    machine_query: MachineQuery,
    service: ServiceConfig,
    *,
    limit: int | None = None,
    page_size: int = 100,
    timeout: float = 30.0,
) -> RowExecutionResult:
    """Paginate the API to collect datapoints into a RowExecutionResult.

    Paginates until `limit` rows, all rows, or the first API error.
    Row unavailability produces ok=false with a structured error (no exception).
    """
    payload = machine_query.to_payload()
    all_datapoints: list[dict] = []
    page_state: dict | None = None
    count_total: int | None = None
    status: int | None = None

    while True:
        current_payload = dict(payload)
        current_payload["pageSize"] = page_size
        if page_state is not None:
            current_payload["pageState"] = page_state

        data = json.dumps(current_payload).encode("utf-8")
        req = urllib.request.Request(
            service.search_url,
            data=data,
            headers={"accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return RowExecutionResult(
                ok=False,
                datapoints=all_datapoints,
                status=e.code,
                error=f"HTTP {e.code}: {e.reason}",
                count_total=count_total,
            )
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return RowExecutionResult(
                ok=False,
                datapoints=all_datapoints,
                error=str(e),
                count_total=count_total,
            )
        except (ValueError, KeyError) as e:
            return RowExecutionResult(
                ok=False,
                datapoints=all_datapoints,
                error=f"bad response: {e}",
                count_total=count_total,
            )

        data_block = body.get("data", {})
        if count_total is None:
            count_total = data_block.get("countTotal")

        rows = data_block.get("datapoints", data_block.get("rows", []))
        if not isinstance(rows, list):
            rows = []
        all_datapoints.extend(rows)

        next_page = data_block.get("pageState") or body.get("pageState")
        if not next_page or not rows:
            break
        if limit is not None and len(all_datapoints) >= limit:
            all_datapoints = all_datapoints[:limit]
            break
        page_state = next_page

    return RowExecutionResult(
        ok=True,
        count_total=count_total,
        datapoints=all_datapoints,
        status=status,
        page_state={"last_page_state": page_state} if page_state else None,
    )
