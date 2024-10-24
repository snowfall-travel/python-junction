from collections.abc import Sequence
from datetime import date
from typing import Any, Literal, NewType, NotRequired, TypedDict


BookingId = NewType("BookingId", str)
BookingPaymentStatus = Literal["requested", "confirmed"]
BookingStatus = Literal["pending", "confirmed", "rejected", "not-ticketed", "error",
                        "cancelled", "fulfilled"]
CancellationId = NewType("CancellationId", str)
CountryCode = NewType("CountryCode", str)  # 2 character ISO 3166-1
Currency = NewType("Currency", str)  # 3 character ISO 4217
DateTime = NewType("DateTime", str)  # RFC 3339
DeliveryOption = Literal["electronic-ticket", "kiosk-collect"]
FlightOfferId = NewType("FlightOfferId", str)
IataCode = NewType("IataCode", str)  # [A-Z]{3}
PlaceId = NewType("PlaceId", str)
PlaceType = Literal["unspecified", "city", "railway-station", "airport", "ferry-port"]
TrainOfferId = NewType("TrainOfferId", str)
OfferId = FlightOfferId | TrainOfferId


class _ErrorDetails(TypedDict):
    detail: str
    pointer: str


class _Error(TypedDict):
    """Common error structure."""

    type: str
    title: str
    status: int
    instance: str
    detail: str
    errors: NotRequired[list[_ErrorDetails]]


class _Coord(TypedDict):
    latitude: float  # -90 to 90
    longitude: float  # -180 to 180


class _Fare(TypedDict):
    type: Literal["unspecified", "economy", "premium", "business", "first"]
    marketingName: str


class _Price(TypedDict):
    currency: Currency
    amount: str


class _PriceBreakdown(TypedDict):
    price: _Price
    breakdownType: Literal["base-fare", "tax"]


class _Airport(TypedDict):
    placeId: PlaceId
    name: str
    iataCode: IataCode
    coordinates: _Coord


class _TrainStation(TypedDict):
    placeId: PlaceId
    name: str
    coordinates: _Coord


class _FlightSegment(TypedDict):
    origin: _Airport
    destination: _Airport
    departureAt: DateTime
    arrivaleAt: DateTime
    fare: _Fare


class _TrainSegment(TypedDict):
    origin: _TrainStation
    destination: _TrainStation
    departureAt: DateTime
    arrivaleAt: DateTime
    fare: _Fare


class Place(TypedDict):
    id: PlaceId
    name: str
    placeTypes: list[PlaceType]
    coordinates: _Coord
    countryCode: CountryCode
    countryName: str
    iataCode: IataCode | None
    timeZone: str
    updatedAt: DateTime


class _Offer(TypedDict):
    expiresAt: DateTime
    price: _Price
    priceBreakdown: list[_PriceBreakdown]
    passportInformation: Literal["not-required", "required", "required-with-issue-date"]


class FlightOffer(_Offer):
    id: FlightOfferId
    segments: list[_FlightSegment]


class TrainOffer(_Offer):
    id: TrainOfferId
    segments: list[_TrainSegment]
    metadata: dict[str, Any]


class FareRule(TypedDict):
    title: str
    body: str


class Fulfillment(TypedDict):
    deliveryOptions: DeliveryOption
    segmentSequence: int


class _Address(TypedDict):
    addressLines: Sequence[str]
    countryCode: str  # 2 letter country code
    postalCode: str
    city: str


class _PassportInformation(TypedDict):
    documentNumber: str
    issueCountry: str  # 2 letter country code
    nationality: str  # 2 letter country code
    expirationDate: date
    issueDate: date


class Passenger(TypedDict):
    dateOfBirth: date
    firstName: str
    lastName: str
    gender: Literal["male", "female"]
    email: str
    phoneNumber: str
    passportInformation: _PassportInformation
    residentialAddress: _Address


class RefundInformation(TypedDict):
    status: Literal["requested", "confirmed"]
    bookingPrice: _Price
    refundAmount: _Price


class Ticket(TypedDict):
    status: Literal["pending", "fulfilled"]
    ticketUrl: str | None
    collectionReference: str | None
