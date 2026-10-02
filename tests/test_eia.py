from src import eia


def test_canonical_ignores_order_duplicates_and_empty_values():
    a = eia.Query(
        route="electricity/retail-sales/",
        data=["price", "price", "sales"],
        frequency="",
        facets={"stateid": ["TX", "CA", "TX"], "sectorid": []},
        start="",
    )
    b = eia.Query(
        route="electricity/retail-sales",
        data=["sales", "price"],
        facets={"stateid": ["CA", "TX"]},
    )
    assert a.canonical() == b.canonical()
