import os
from typing import AsyncIterator

import pytest

@pytest.fixture
async def client() -> AsyncIterator[JunctionClient]:
    async with JunctionClient(os.environ["JUNCTION_API_KEY"]) as client:
        yield client
