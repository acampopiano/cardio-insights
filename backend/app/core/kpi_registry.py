from dataclasses import dataclass
import json
from pathlib import Path
from threading import Lock

from app.core.config import get_settings


@dataclass
class DynamicKpi:
    key: str
    label: str
    description: str
    sql_query_template: str
    default_granularity: str = "month"


class KpiRegistry:
    """Registro de KPIs dinamicos respaldado en archivo JSON compartido."""

    def __init__(self) -> None:
        self._items: dict[str, DynamicKpi] = {}
        self._lock = Lock()
        settings = get_settings()
        backend_root = Path(__file__).resolve().parents[2]
        self._store_path = backend_root / settings.dynamic_kpis_file
        self._load_from_store()

    def _load_from_store(self) -> None:
        if not self._store_path.exists():
            return

        raw_items = json.loads(self._store_path.read_text(encoding="utf-8"))
        if not isinstance(raw_items, list):
            return

        loaded: dict[str, DynamicKpi] = {}
        for entry in raw_items:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("key") or "").strip()
            label = str(entry.get("label") or "").strip()
            description = str(entry.get("description") or "").strip()
            sql_query_template = str(entry.get("sql_query_template") or "").strip()
            default_granularity = str(entry.get("default_granularity") or "month").strip().lower()
            if not key or not label or not description or not sql_query_template:
                continue
            if default_granularity not in {"day", "week", "month", "year"}:
                default_granularity = "month"
            loaded[key] = DynamicKpi(
                key=key,
                label=label,
                description=description,
                sql_query_template=sql_query_template,
                default_granularity=default_granularity,
            )

        self._items = loaded

    def _save_to_store(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "key": item.key,
                "label": item.label,
                "description": item.description,
                "sql_query_template": item.sql_query_template,
                "default_granularity": item.default_granularity,
            }
            for item in self._items.values()
        ]
        self._store_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def upsert(self, item: DynamicKpi) -> None:
        with self._lock:
            self._items[item.key] = item
            self._save_to_store()

    def get(self, key: str) -> DynamicKpi | None:
        with self._lock:
            return self._items.get(key)

    def remove(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)
            self._save_to_store()

    def list_all(self) -> list[DynamicKpi]:
        with self._lock:
            return list(self._items.values())


kpi_registry = KpiRegistry()
