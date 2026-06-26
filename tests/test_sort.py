"""Sort helper tests."""

from stremio_playlists.sort.sorter import sort_indices_by_year


def test_sort_years_asc():
    years = [1999, 1982, 2010]
    idx = sort_indices_by_year(years, ascending=True)
    assert [years[i] for i in idx] == [1982, 1999, 2010]


def test_sort_years_desc():
    years = [1999, 1982, 2010]
    idx = sort_indices_by_year(years, ascending=False)
    assert [years[i] for i in idx] == [2010, 1999, 1982]
