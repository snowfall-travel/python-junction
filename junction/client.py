import asyncio
import json
import sys
from collections import deque
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from functools import partial
from textwrap import indent
from types import TracebackType
from typing import Any, Generic, NoReturn, Self, TypedDict, TypeVar

import aiojobs
from aiohttp import ClientResponse, ClientResponseError, ClientSession, ContentTypeError
from yarl import URL

from junction import typedefs as t


_T = TypeVar("_T")

PROD = "api.junction.travel"
SANDBOX = "content-api.sandbox.junction.dev"


class _Booking(TypedDict):
    id: t.BookingId
    status: t.BookingStatus
    passengers: list[t.Passenger]
    price: t._Price
    ticketInformation: list[t.Ticket]
    fareRules: list[t.FareRule]


class _BookingResult(TypedDict):
    booking: list[_Booking]
    fulfillmentInformation: list[t.Fulfillment]


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


class Cancellation:
    _id: t.CancellationId
    _refund: t.RefundInformation

    def __init__(self, client: ClientSession, booking_id: t.BookingId, host: str = PROD):
        self._booking_id = booking_id
        self._client = client
        self._confirmed = False
        self._host = host  # TODO: Use base_url in ClientSession and remove host parameter here.

    @property
    def id(self) -> t.CancellationId:
        return self._id

    @property
    def refund(self) -> t.RefundInformation:
        return self._refund

    async def confirm(self) -> None:
        path = f"/cancellations/{self._id}/confirm"
        url = URL.build(scheme="https", host=self._host, path=path)
        async with self._client.post(url) as resp:
            if not resp.ok:
                await raise_error(resp)
            result = await resp.json()
            self._refund = result["refundInformation"]

    async def recreate(self) -> None:
        if self._confirmed:
            raise RuntimeError("Booking already confirmed")

        url = URL.build(scheme="https", host=self._host, path="/cancellations/request")
        body = {"bookingId": self._booking_id}
        async with self._client.post(url, json=body) as resp:
            if not resp.ok:
                await raise_error(resp)
            result = await resp.json()
            self._id = result["id"]
            self._refund = result["refundInformation"]


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


class JunctionClient:
    '''
    This is the JunctionClient. Use this class to make calls to the JunctionAPI. 
    You can use this to do a search for places and the use the placeids to do FlightSearch, TrainSearch, etc.
    '''
    def __init__(self, api_key: str, host: str = PROD):
        self._api_key = api_key
        self._host = host

    def search_places(
        self,
        name_like: str | None = None,
        place_types: Iterable[t.PlaceType] | None = None,
        iata: str | None = None,
        coords: tuple[float, float, int] | None = None,
        search_within: t.PlaceId | None = None
    ) -> ResultsIterator[t.Place]:
        query: dict[str, int | str] = {"page[limit]": 100}
        if name_like is not None:
            query["filter[name][like]"] = name_like
        if place_types is not None:
            query["filter[type][eq]"] = ",".join(place_types)
        if iata is not None:
            query["filter[iata][eq]"] = iata
        if coords is not None:
            query["query[coordinates]"] = ",".join(map(str, coords))
        if search_within is not None:
            query["query[placeToSearchWithin]"] = search_within

        url = URL.build(scheme="https", host=self._host, path="/places", query=query)
        return ResultsIterator[t.Place](self._client, self._scheduler, url)

    async def flight_search(
        self,
        origin: t.PlaceId,
        destination: t.PlaceId,
        depart_after: datetime,
        passenger_birth_dates: Iterable[date]
    ) -> ResultsIterator[t.FlightOffer]:
        url = URL.build(scheme="https", host=self._host, path="/flight-searches")
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
        url = URL.build(scheme="https", host=self._host, path="/train-searches")
        ages = tuple({"dateOfBirth": d} for d in passenger_birth_dates)
        query = {"originId": origin, "destinationId": destination,
                 "departureAfter": depart_after, "passengerAges": ages,
                 "returnDepartureAfter": return_depart_after}
        async with self._client.post(url, json=query) as resp:
            if not resp.ok:
                await raise_error(resp)
            next_url = resp.headers["Location"]
        return ResultsIterator[t.TrainOffer](self._client, self._scheduler, next_url)

    async def create_booking(self, offer: t.OfferId, passengers: Iterable[t.Passenger]) -> Any:
        url = URL.build(scheme="https", host=self._host, path="/bookings")
        body = {"offerId": offer, "passengers": passengers}
        async with self._client.post(url, json=body) as resp:
            if not resp.ok:
                await raise_error(resp)
            return await resp.json()

    async def confirm_booking(self, booking_id: t.BookingId, fulfillment: Sequence[tuple[t.DeliveryOption, int]]) -> t.BookingPaymentStatus:
        url = URL.build(scheme="https", host=self._host, path=f"/bookings/{booking_id}/confirm")
        body = {"fulfillmentChoices": tuple({"deliveryOption": d, "segmentSequence": s} for d, s in fulfillment)}
        async with self._client.post(url, json=body) as resp:
            if not resp.ok:
                await raise_error(resp)

            result = await resp.json()
        return result["paymentStatus"]

    async def get_booking(self, booking_id: t.BookingId) -> Any:
        url = URL.build(scheme="https", host=self._host, path=f"/bookings/{booking_id}")
        async with self._client.get(url) as resp:
            if not resp.ok:
                await raise_error(resp)
            return await resp.json()

    async def cancel_booking(self, booking_id: t.BookingId) -> Cancellation:
        cancellation = Cancellation(self._client, booking_id, host=self._host)
        await cancellation.recreate()
        return cancellation

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
