import datetime

from junction import JunctionClient, Passenger, PlaceId

async def test_round_trip(client: JunctionClient) -> None:
    orig = PlaceId("place_01j804c5h1ew3ask9eh2znw3pz")
    dest = PlaceId("place_01j804pa0ffcrva5gpd21nmqhk")
    day = datetime.date.today() + datetime.timedelta(days=7)
    depart = datetime.datetime.combine(day, datetime.time(12, 30), datetime.UTC)
    birth = datetime.date(2000, 1, 1)
    offer_iter = await client.train_search(orig, dest, depart, depart + datetime.timedelta(days=2), (birth,))
    outbound_offer = await anext(offer_iter)
    assert outbound_offer["inboundStepRequired"]
    return_offer = await anext(client.get_train_offers(offer_iter.id, outbound=outbound_offer["id"]))
    assert not return_offer["inboundStepRequired"]

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
    booking = await client.create_booking(return_offer["id"], (passenger,))
    assert float(booking["booking"]["price"]["amount"]) == float(return_offer["price"]["amount"])

async def test_cancellation(client: JunctionClient) -> None:
    orig = PlaceId("place_01j804c5h1ew3ask9eh2znw3pz")
    dest = PlaceId("place_01j804922hfcws9mffxbj8tsv3")
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
    await client.confirm_booking(booking["booking"]["id"], tuple((f["deliveryOptions"][0], f["segmentSequence"]) for f in booking["fulfillmentInformation"]))

    cancellation = await client.cancel_booking(booking["booking"]["id"])
    assert cancellation.refund["status"] == "requested"
    assert float(cancellation.refund["bookingPrice"]["amount"]) > 0
    refund_amount = cancellation.refund["refundAmount"]["amount"]
    assert float(refund_amount) > 0

    await cancellation.confirm()
    assert cancellation.refund["status"] == "confirmed"
    assert cancellation.refund["refundAmount"]["amount"] == refund_amount
