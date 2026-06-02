from dataclasses import dataclass
from threading import Lock


@dataclass
class DynamicKpi:
    key: str
    label: str
    description: str
    sql_query_template: str
    default_granularity: str = "month"


class KpiRegistry:
    """Registro en memoria de KPIs dinamicos creados desde UI/Swagger."""

    def __init__(self) -> None:
        self._items: dict[str, DynamicKpi] = {}
        self._lock = Lock()

    def upsert(self, item: DynamicKpi) -> None:
        with self._lock:
            self._items[item.key] = item

    def get(self, key: str) -> DynamicKpi | None:
        with self._lock:
            return self._items.get(key)

    def remove(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)

    def list_all(self) -> list[DynamicKpi]:
        with self._lock:
            return list(self._items.values())


kpi_registry = KpiRegistry()
