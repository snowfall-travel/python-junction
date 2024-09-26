import os
from typing import AsyncIterator

import pytest

from junction import SANDBOX, JunctionClient

@pytest.fixture
async def client() -> AsyncIterator[JunctionClient]:
    key = os.environ["JUNCTION_API_KEY"]
    async with JunctionClient(key, SANDBOX) as client:
        yield client
