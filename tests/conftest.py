import os
from typing import AsyncIterator

import pytest

from junction import JunctionClient

@pytest.fixture
async def client() -> AsyncIterator[JunctionClient]:
    async with JunctionClient(os.environ["JUNCTION_API_KEY"]) as client:
        yield client
