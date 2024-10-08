import datetime

from junction import JunctionClient, Passenger

async def test_cancellation(client: JunctionClient) -> None:
    orig = "place_01j44f6jw3erbr4rgna3xdtvxn"
    dest = "place_01j44f3vfje1pbbr16etj2s26c"
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

    refund = await client.cancel_booking(booking.id)
    assert refund["status"] == "requested"
    assert float(refund["bookingPrice"]["amount"]) > 0
    refund_amount = refund["refundAmount"]["amount"]
    assert float(refund_amount) > 0

    refund = await client.cancel_booking_confirm(cancellation_id)
    assert refund["status"] == "confirmed"
    assert refund["refundAmount"]["amount"] == refund_amount
