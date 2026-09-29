"""Station catalogue shipped with the integration.

stations.json is taken from the mittog.dk web app: code -> [name, services], where
services lists the boards ("stog", "tog") mittog.dk offers for that station. Codes
without services are still known by name (they show up as destinations and stops).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
import json
from pathlib import Path

# mittog.dk reports a couple of stations under an internal code.
ALIASES = {"HGL": "KK", "HTAA": "HTÅ"}


@dataclass(frozen=True, slots=True)
class Station:
    code: str
    name: str
    services: tuple[str, ...]


@cache
def _catalogue() -> dict[str, Station]:
    raw = json.loads((Path(__file__).parent / "stations.json").read_text(encoding="utf-8"))
    return {code: Station(code, name, tuple(services)) for code, (name, services) in raw.items()}


def load_catalogue() -> None:
    """Read the catalogue; call from an executor before first use on the event loop."""
    _catalogue()


def normalize(code: str) -> str:
    return ALIASES.get(code, code)


def get(code: str) -> Station | None:
    return _catalogue().get(normalize(code))


def name(code: str) -> str:
    station = get(code)
    return station.name if station else code.lstrip("%")


def for_service(service: str) -> list[Station]:
    return sorted(
        (s for s in _catalogue().values() if service in s.services),
        key=lambda s: s.name.casefold(),
    )
