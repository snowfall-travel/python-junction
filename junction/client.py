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
    _status: t.BookingStatus
    _ticket: t.Ticket
    _fare_rules: tuple[t.FareRule, ...]
    _fulfillment: tuple[t.Fulfillment, ...]

    def __init__(self, client: ClientSession, offer: t.OfferId, passengers: tuple[t.Passenger, ...], host: str = PROD):
        self._client = client
        self._host = host  # TODO: Use base_url in ClientSession and remove host parameter here.
        self._offer = offer
        self._passengers = passengers
        self._confirmed = False

    @property
    def confirmed(self) -> bool:
        return self._confirmed

    @property
    def fare_rules(self) -> tuple[t.FareRule, ...]:
        return self._fare_rules

    @property
    def fulfillment(self) -> tuple[t.Fulfillment, ...]:
        return self._fulfillment

    @property
    def id(self) -> t.BookingId:
        return self._id

    @property
    def passengers(self) -> tuple[t.Passenger, ...]:
        return self._passengers

    @property
    def price(self) -> tuple[str, str]:
        return self._price

    @property
    def status(self) -> t.BookingStatus:
        return self._status

    @property
    def ticket(self) -> t.Ticket:
        return self._ticket

    def _update_attrs(self, result: _BookingResult) -> None:
        self._fulfillment = tuple(result["fulfillmentInformation"])
        booking = result["booking"]
        self._id = booking["id"]
        self._fare_rules = tuple(booking["fareRules"])
        self._passengers = tuple(booking["passengers"])
        self._price = (booking["price"]["amount"], booking["price"]["currency"])
        self._status = booking["status"]
        self._ticket = booking["ticketInformation"]

    async def confirm(self, fulfillment: Sequence[t.DeliveryOption]) -> t.BookingPaymentStatus:
        if len(fulfillment) != len(self._fulfillment):
            raise ValueError("Wrong number of fillment choices")

        url = URL.build(scheme="https", host=self._host, path=f"/bookings/{self._id}/confirm")
        body = {"fulfillmentChoices": tuple({"deliveryOption": c, "segmentSequence": f["segmentSequence"]} for f, c in zip(self._fulfillment, fulfillment))}
        async with self._client.post(url, json=body) as resp:
            if not resp.ok:
                await raise_error(resp)

            result = await resp.json()
            self._update_attrs(result)
            self._confirmed = True
        return result["paymentStatus"]

    async def refresh(self) -> None:
        if self._confirmed:
            raise RuntimeError("Booking already confirmed")

        url = URL.build(scheme="https", host=self._host, path="/bookings")
        body = {"offerId": self._offer, "passengers": self._passengers}
        async with self._client.post(url, json=body) as resp:
            if not resp.ok:
                await raise_error(resp)

            result = await resp.json()
            self._update_attrs(result)


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

    async def create_booking(self, offer: t.OfferId, passengers: Iterable[t.Passenger]) -> Booking:
        booking = Booking(self._client, offer, tuple(passengers), host=self._host)
        await booking.refresh()
        return booking

    async def cancel_booking(self, booking_id: t.BookingId) -> t.RefundInformation:
        path = f"/bookings/{booking_id}/request-cancellation"
        url = URL.build(scheme="https", host=self._host, path=path)
        async with self._client.post(url) as resp:
            if not resp.ok:
                await raise_error(resp)
            result = await resp.json()
        return result["refundInformation"]  # type: ignore[no-any-return]

    async def cancel_booking_confirm(self, booking_id: t.BookingId) -> t.RefundInformation:
        path = f"/bookings/{booking_id}/confirm-cancellation"
        url = URL.build(scheme="https", host=self._host, path=path)
        async with self._client.post(url) as resp:
            if not resp.ok:
                await raise_error(resp)
            result = await resp.json()
        return result["refundInformation"]  # type: ignore[no-any-return]

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
