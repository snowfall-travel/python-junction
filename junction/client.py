import asyncio
import json
import sys
from collections import deque
from collections.abc import Iterable
from datetime import date, datetime
from functools import partial
from textwrap import indent
from types import TracebackType
from typing import Any, Generic, NoReturn, TypeVar

import aiojobs
from aiohttp import ClientResponse, ClientResponseError, ClientSession, ContentTypeError
from yarl import URL

from junction import typedefs as t

# Requires 3.10+
if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing import Any as Self


_T = TypeVar("_T")

HOST = "content-api.junction.dev"


class CustomEncoder(json.JSONEncoder):
    def default(self, obj: object) -> Any:
        if isinstance(obj, date):
            return obj.isoformat()

        return super().default(obj)


async def raise_error(resp: ClientResponse) -> NoReturn:
    try:
        result = await resp.json()
    except ContentTypeError:
        msg = repr(await resp.read())
    else:
        msg = f"{result['title']}: {result['detail']}"
        if result.get("errors"):
            msg += "\n" + indent("\n".join(f"- {e['pointer']}: {e['detail']}" for e in result["errors"]), "  ")
    raise ClientResponseError(resp.request_info, resp.history, status=resp.status, message=msg, headers=resp.headers)


class ResultsIterator(Generic[_T]):
    def __init__(self, client: ClientSession, scheduler: aiojobs.Scheduler, next_url: URL | str):
        self._client = client
        self._scheduler = scheduler
        self._results: deque[_T] = deque()
        self._task: aiojobs.Job[None] | None = None
        self._next = next_url

    async def start(self) -> None:
        assert self._next and not self._task
        await self._fetch()

    async def _fetch(self) -> None:
        while True:
            async with self._client.get(self._next) as resp:
                if resp.status == 202:  # Results pending, need to wait and retry.
                    await asyncio.sleep(5)
                    continue
                if not resp.ok:
                    await raise_error(resp)

                result = await resp.json()
                if not result["items"]:
                    raise StopAsyncIteration()
                self._results.extend(result["items"])
                self._next = result["links"]["next"]
                break
        self._task = None

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> _T:
        if self._next and not self._task and len(self._results) < 90:
            self._task = await self._scheduler.spawn(self._fetch())

        if not self._results:
            if self._task:
                await self._task.wait()
            else:
                raise StopAsyncIteration()

        return self._results.popleft()


class Booking:
    _id: t.BookingId

    def __init__(self, client: ClientSession, offer: t.OfferId, passengers: tuple[t.Passenger, ...]):
        self._client = client
        self._offer = offer
        self._passengers = passengers
        self._confirmed = False

    @property
    def confirmed(self) -> bool:
        return self._confirmed

    @property
    def id(self) -> t.BookingId:
        return self._id

    @property
    def passengers(self) -> tuple[t.Passenger, ...]:
        return self._passengers

    @property
    def price(self) -> tuple[str, str]:
        return self._price

    async def confirm(self) -> None:
        url = URL.build(scheme="https", host=HOST, path="/bookings")
        body = {"offerId": self._offer, "passengers": self._passengers}
        async with self._client.post(url, json=body) as resp:
            if not resp.ok:
                await raise_error(resp)

            result = await resp.json()
            self._id = result["id"]
            self._passengers = result["passengers"]
            self._price = (result["price"]["amount"], result["price"]["currency"])
            self._confirmed = True

    async def refresh(self) -> None:
        if self._confirmed:
            raise RuntimeError("Booking already confirmed")

        url = URL.build(scheme="https", host=HOST, path="/bookings")
        body = {"offerId": self._offer, "passengers": self._passengers}
        #print(json.dumps(body, cls=CustomEncoder))
        async with self._client.post(url, json=body) as resp:
            if not resp.ok:
                await raise_error(resp)

            result = await resp.json()
            self._id = result["id"]
            self._passengers = result["passengers"]
            self._price = (result["price"]["amount"], result["price"]["currency"])


class JunctionClient:
    '''
    This is the JunctionClient. Use this class to make calls to the JunctionAPI. 
    You can use this to do a search for places and the use the placeids to do FlightSearch, TrainSearch, etc.
    '''
    def __init__(self, api_key: str):
        self._api_key = api_key

    def search_places(
        self,
        name_like: str | None = None,
        place_type: t.PlaceType | None = None,
        iata: str | None = None,
        coords: tuple[float, float, int] | None = None,
        search_within: t.PlaceId | None = None
    ) -> ResultsIterator[t.Place]:
        query: dict[str, int | str] = {"page[limit]": 100}
        if name_like is not None:
            query["filter[name][like]"] = name_like
        if place_type is not None:
            query["filter[type][eq]"] = place_type
        if iata is not None:
            query["filter[iata][eq]"] = iata
        if coords is not None:
            query["query[coordinates]"] = ",".join(map(str, coords))
        if search_within is not None:
            query["query[placeToSearchWithin]"] = search_within

        url = URL.build(scheme="https", host=HOST, path="/places", query=query)
        return ResultsIterator[t.Place](self._client, self._scheduler, url)

    async def flight_search(
        self,
        origin: t.PlaceId,
        destination: t.PlaceId,
        depart_after: datetime,
        passenger_birth_dates: Iterable[date]
    ) -> ResultsIterator[t.FlightOffer]:
        url = URL.build(scheme="https", host=HOST, path="/flight-searches")
        ages = tuple({"dateOfBirth": d} for d in passenger_birth_dates)
        query = {"originId": origin, "destinationId": destination,
                 "departureAfter": depart_after, "passengerAges": ages}
        async with self._client.post(url, json=query) as resp:
            if not resp.ok:
                await raise_error(resp)
            next_url = resp.headers["Location"]
        return ResultsIterator[t.FlightOffer](self._client, self._scheduler, next_url)

    async def train_search(
        self,
        origin: t.PlaceId,
        destination: t.PlaceId,
        depart_after: datetime,
        return_depart_after: datetime | None,
        passenger_birth_dates: Iterable[date]
    ) -> ResultsIterator[t.TrainOffer]:
        url = URL.build(scheme="https", host=HOST, path="/train-searches")
        ages = tuple({"dateOfBirth": d} for d in passenger_birth_dates)
        query = {"originId": origin, "destinationId": destination,
                 "departureAfter": depart_after, "passengerAges": ages,
                 "returnDepartureAfter": return_depart_after}
        async with self._client.post(url, json=query) as resp:
            if not resp.ok:
                await raise_error(resp)
            next_url = resp.headers["Location"]
        return ResultsIterator[t.TrainOffer](self._client, self._scheduler, next_url)

    async def create_booking(self, offer: t.OfferId, passengers: Iterable[t.Passenger]) -> Booking:
        booking = Booking(self._client, offer, tuple(passengers))
        await booking.refresh()
        return booking

    async def __aenter__(self) -> Self:
        self._client = ClientSession(headers={"x-api-key": self._api_key}, json_serialize=partial(json.dumps, cls=CustomEncoder))
        self._scheduler = aiojobs.Scheduler(wait_timeout=0)
        await self._client.__aenter__()
        await self._scheduler.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None
    ) -> None:
        await self._scheduler.__aexit__(exc_type, exc_val, exc_tb)
        await self._client.__aexit__(exc_type, exc_val, exc_tb)
