"""Optional Numba-accelerated year sorting for large playlists."""

from __future__ import annotations

from typing import Sequence

try:
    from numba import njit

    @njit(cache=True)
    def _sort_years_numba(years: list[int], ascending: bool) -> list[int]:
        indices = list(range(len(years)))
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                a, b = years[indices[i]], years[indices[j]]
                swap = (a > b) if ascending else (a < b)
                if swap:
                    indices[i], indices[j] = indices[j], indices[i]
        return indices

    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

    def _sort_years_numba(years: list[int], ascending: bool) -> list[int]:
        return sorted(range(len(years)), key=lambda i: years[i], reverse=not ascending)


def sort_indices_by_year(years: Sequence[int | None], ascending: bool = True) -> list[int]:
    filled = [y if y is not None else (0 if ascending else 9999) for y in years]
    return _sort_years_numba(filled, ascending)
