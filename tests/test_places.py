from junction import JunctionClient

async def test_no_results_iter(client: JunctionClient) -> None:
    no_result = False

    async for place in client.search_places(coords=(51.01, -32.51, 50)):
        assert False
    else:
        no_result = True

    assert no_result
