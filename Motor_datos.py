"""
Motor de datos para widget de vocabulario japonés.
Descarga JSON remoto, cachea en memoria y expone selección aleatoria
sin repetir el ID inmediatamente anterior.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from typing import Any, Optional

import requests

JSON_URL = (
    "https://raw.githubusercontent.com/H4r0l05ky/ProyectoNihon/"
    "refs/heads/main/KanjisPalabrillasydatos.json"
)
REQUEST_TIMEOUT = 10  # segundos


@dataclass(frozen=True, slots=True)
class VocabItem:
    id: int
    termino: str
    pronunciacion: str
    significados: list[str]
    ejemplo: dict[str, str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VocabItem":
        return cls(
            id=data["id"],
            termino=data["termino"],
            pronunciacion=data["pronunciacion"],
            significados=data["significados"],
            ejemplo=data["ejemplo"],
        )


class VocabRepository:
    """Descarga y almacena en memoria el vocabulario remoto."""

    def __init__(self, url: str = JSON_URL, timeout: int = REQUEST_TIMEOUT) -> None:
        self._url = url
        self._timeout = timeout
        self._items: list[VocabItem] = []

    def load(self) -> None:
        try:
            response = requests.get(self._url, timeout=self._timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Fallo al descargar el JSON: {exc}") from exc

        try:
            raw_data = response.json()
        except ValueError as exc:
            raise RuntimeError("El contenido recibido no es JSON válido.") from exc

        if not isinstance(raw_data, list) or not raw_data:
            raise RuntimeError("El JSON recibido está vacío o mal formado.")

        self._items = [VocabItem.from_dict(entry) for entry in raw_data]

    @property
    def items(self) -> list[VocabItem]:
        return self._items

    def __len__(self) -> int:
        return len(self._items)


class VocabSelector:
    """Selecciona un elemento aleatorio evitando repetir el ID previo."""

    def __init__(self, repository: VocabRepository) -> None:
        self._repository = repository
        self._last_id: Optional[int] = None

    def pick(self) -> VocabItem:
        items = self._repository.items
        if not items:
            raise RuntimeError("El repositorio no tiene elementos cargados.")

        if len(items) == 1:
            selected = items[0]
        else:
            candidates = [item for item in items if item.id != self._last_id]
            selected = random.choice(candidates)

        self._last_id = selected.id
        return selected


def print_item(item: VocabItem) -> None:
    significados = ", ".join(item.significados)
    print("=" * 40)
    print(f"ID            : {item.id}")
    print(f"Término       : {item.termino}")
    print(f"Pronunciación : {item.pronunciacion}")
    print(f"Significados  : {significados}")
    print(f"Ejemplo (JP)  : {item.ejemplo.get('oracion', '')}")
    print(f"Ejemplo (ES)  : {item.ejemplo.get('traduccion', '')}")
    print("=" * 40)


def main() -> None:
    repository = VocabRepository()
    try:
        repository.load()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Vocabulario cargado: {len(repository)} elementos.\n")

    selector = VocabSelector(repository)

    # Prueba de verificación: dos selecciones consecutivas
    for _ in range(2):
        item = selector.pick()
        print_item(item)


if __name__ == "__main__":
    main()