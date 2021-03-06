import geopandas as gp
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import Polygon

from regionmask import Regions, from_geopandas, mask_geopandas
from regionmask.core._geopandas import (
    _check_duplicates,
    _construct_abbrevs,
    _enumerate_duplicates,
)

# create dummy Polygons for testing
poly1 = Polygon(((0, 0), (0, 1), (1, 1.0), (1, 0)))
poly2 = Polygon(((0, 1), (0, 2), (1, 2.0), (1, 1)))
geometries = [poly1, poly2]


@pytest.fixture
def geodataframe_clean():

    numbers = [1, 2]
    names = ["Unit Square1", "Unit Square2"]
    abbrevs = ["uSq1", "uSq2"]

    d = dict(names=names, abbrevs=abbrevs, numbers=numbers, geometry=geometries)

    return gp.GeoDataFrame.from_dict(d)


@pytest.fixture
def geodataframe_missing():

    numbers = [1, None]
    names = ["Unit Square1", None]
    abbrevs = ["uSq1", None]

    d = dict(names=names, abbrevs=abbrevs, numbers=numbers, geometry=geometries)

    return gp.GeoDataFrame.from_dict(d)


@pytest.fixture
def geodataframe_duplicates():

    numbers = [1, 1]
    names = ["Unit Square", "Unit Square"]
    abbrevs = ["uSq1", "uSq1"]

    d = dict(names=names, abbrevs=abbrevs, numbers=numbers, geometry=geometries)

    return gp.GeoDataFrame.from_dict(d)


def test_from_geopandas_wrong_input():
    with pytest.raises(
        TypeError, match="`geodataframe` must be a geopandas 'GeoDataFrame'"
    ):
        from_geopandas(None)


def test_from_geopandas_use_columns(geodataframe_clean):

    result = from_geopandas(
        geodataframe_clean,
        numbers="numbers",
        names="names",
        abbrevs="abbrevs",
        name="name",
        source="source",
    )

    assert isinstance(result, Regions)

    assert result.polygons[0].equals(poly1)
    assert result.polygons[1].equals(poly2)
    assert result.numbers == [1, 2]
    assert result.names == ["Unit Square1", "Unit Square2"]
    assert result.abbrevs == ["uSq1", "uSq2"]
    assert result.name == "name"
    assert result.source == "source"


def test_from_geopandas_default(geodataframe_clean):

    result = from_geopandas(geodataframe_clean)

    assert isinstance(result, Regions)

    assert result.polygons[0].equals(poly1)
    assert result.polygons[1].equals(poly2)
    assert result.numbers == [0, 1]
    assert result.names == ["Region0", "Region1"]
    assert result.abbrevs == ["r0", "r1"]
    assert result.name == "unnamed"
    assert result.source is None


@pytest.mark.parametrize("arg", ["names", "abbrevs", "numbers"])
def test_from_geopandas_missing_error(geodataframe_missing, arg):

    with pytest.raises(
        ValueError, match="{} cannot contain missing values".format(arg)
    ):
        from_geopandas(geodataframe_missing, **{arg: arg})


@pytest.mark.parametrize("arg", ["names", "abbrevs", "numbers"])
def test_from_geopandas_duplicates_error(geodataframe_duplicates, arg):

    with pytest.raises(
        ValueError, match="{} cannot contain duplicate values".format(arg)
    ):
        from_geopandas(geodataframe_duplicates, **{arg: arg})


@pytest.mark.parametrize("arg", ["names", "abbrevs", "numbers"])
def test_from_geopandas_column_missing(geodataframe_clean, arg):

    with pytest.raises(KeyError):
        from_geopandas(geodataframe_clean, **{arg: "not_a_column"})


series_duplicates = pd.Series([1, 1, 2, 3, 4])
series_unique = pd.Series(list(np.arange(2, 5)))


def test_check_duplicates_raise_ValueError():
    with pytest.raises(ValueError):
        _check_duplicates(series_duplicates, "name")


def test_check_duplicates_return_True():
    assert _check_duplicates(series_unique, "name")


def test_construct_abbrevs_wrong_name(geodataframe_clean):
    with pytest.raises(KeyError):
        _construct_abbrevs(geodataframe_clean, "wrong_name")


def test_construct_abbrevs_two_words(geodataframe_clean):
    abbrevs = _construct_abbrevs(geodataframe_clean, "names")
    assert abbrevs[0] == "UniSqu0"
    assert abbrevs[1] == "UniSqu1"


def test_enumerate_duplicates():

    data = pd.Series(["a", "a", "b"])

    result = _enumerate_duplicates(data)
    expected = pd.Series(["a0", "a1", "b"])
    pd.testing.assert_series_equal(result, expected)

    result = _enumerate_duplicates(data, keep="first")
    expected = pd.Series(["a", "a0", "b"])
    pd.testing.assert_series_equal(result, expected)

    result = _enumerate_duplicates(data, keep="last")
    expected = pd.Series(["a0", "a", "b"])
    pd.testing.assert_series_equal(result, expected)


def test_construct_abbrevs():
    strings = ["A", "Bcef", "G[hi]", "J(k)", "L.mn", "Op/Qr", "Stuvw-Xyz"]

    df = pd.DataFrame(strings, columns=["strings"])
    result = _construct_abbrevs(df, "strings")
    expected = ["A", "Bce", "Ghi", "Jk", "Lmn", "OpQr", "StuXyz"]
    for i in range(len(result)):
        assert result[i] == expected[i]


# ==============================================================================
# uses the same function as `Regions.mask` - only do minimal tests here


def expected_mask(a=0, b=1, fill=np.NaN):
    return np.array([[a, fill], [b, fill]])


lon = [0.5, 1.5]
lat = [0.5, 1.5]


def test_mask_geopandas_wrong_input():

    with pytest.raises(TypeError, match="'GeoDataFrame' or 'GeoSeries'"):
        mask_geopandas(None, lon, lat)


def test_mask_geopandas_raises_legacy(geodataframe_clean):

    with pytest.raises(ValueError, match="method 'legacy' not supported"):
        mask_geopandas(geodataframe_clean, lon, lat, method="legacy")


@pytest.mark.parametrize("method", ["rasterize", "shapely"])
def test_mask_geopandas(geodataframe_clean, method):

    expected = expected_mask()
    result = mask_geopandas(geodataframe_clean, lon, lat, method=method)

    assert isinstance(result, xr.DataArray)
    assert np.allclose(result, expected, equal_nan=True)
    assert np.all(np.equal(result.lat.values, lat))
    assert np.all(np.equal(result.lon.values, lon))


@pytest.mark.parametrize("method", ["rasterize", "shapely"])
def test_mask_geopandas_numbers(geodataframe_clean, method):

    expected = expected_mask(1, 2)
    result = mask_geopandas(
        geodataframe_clean, lon, lat, method=method, numbers="numbers"
    )

    assert isinstance(result, xr.DataArray)
    assert np.allclose(result, expected, equal_nan=True)
    assert np.all(np.equal(result.lat.values, lat))
    assert np.all(np.equal(result.lon.values, lon))


def test_mask_geopandas_wrong_numbers(geodataframe_clean):

    with pytest.raises(KeyError):
        mask_geopandas(geodataframe_clean, lon, lat, numbers="not_a_column")


def test_mask_geopandas_missing_error(geodataframe_missing):

    with pytest.raises(ValueError, match="cannot contain missing values"):
        mask_geopandas(geodataframe_missing, lon, lat, numbers="numbers")


def test_mask_geopandas_duplicates_error(geodataframe_duplicates):

    with pytest.raises(ValueError, match="cannot contain duplicate values"):
        mask_geopandas(geodataframe_duplicates, lon, lat, numbers="numbers")
