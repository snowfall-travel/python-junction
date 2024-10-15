import datetime

from junction import JunctionClient, Passenger, PlaceId

async def test_cancellation(client: JunctionClient) -> None:
    orig = PlaceId("place_01j804c5h1ew3ask9eh2znw3pz")
    dest = PlaceId("place_01j804pa0ffcrva5gpd21nmqhk")
    day = datetime.date.today() + datetime.timedelta(days=7)
    depart = datetime.datetime.combine(day, datetime.time(12, 30), datetime.UTC)
    birth = datetime.date(2000, 1, 1)
    offer = await anext(await client.train_search(orig, dest, depart, None, (birth,)))

    passenger: Passenger = {
        "dateOfBirth": birth,
        "firstName": "foo",
        "lastName": "bar",
        "gender": "male",
        "email": "foo@bar.com",
        "phoneNumber": "+4407770000001",
        "passportInformation": {
            "documentNumber": "1",
            "issueCountry": "GB",
            "nationality": "GB",
            "expirationDate": datetime.date.today() + datetime.timedelta(days=365),
            "issueDate": datetime.date.today() - datetime.timedelta(days=365)
        },
        "residentialAddress": {
            "addressLines": ("1 Foo Road",),
            "countryCode": "GB",
            "postalCode": "BN1",
            "city": "Brighton"
        }
    }
    booking = await client.create_booking(offer["id"], (passenger,))
    assert not booking.confirmed
    await booking.confirm()
    assert booking.confirmed

    refund = await client.cancel_booking(booking.id)  # type: ignore[unreachable]
    assert refund["status"] == "requested"
    assert float(refund["bookingPrice"]["amount"]) > 0
    refund_amount = refund["refundAmount"]["amount"]
    assert float(refund_amount) > 0

    refund = await client.cancel_booking_confirm(cancellation_id)
    assert refund["status"] == "confirmed"
    assert refund["refundAmount"]["amount"] == refund_amount
