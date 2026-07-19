from typing import Any, List, Optional

import requests
from langchain_core.tools import tool


HOTEL_API_BASE = "https://standing-fish-574.convex.site/hotels"
FLIGHT_API_BASE = "https://standing-fish-574.convex.site/flights"


def _fetch_json(url: str, params: Optional[dict] = None) -> Any:
    try:
        response = requests.get(
            url,
            params=params,
        )
        return response.json()

    except Exception as e:
        return None


@tool
def get_hotels() -> List[dict]:
    """
    Get a list of all available hotels.
    Use this when the user asks to show/list all hotels.
    """
    data = _fetch_json(HOTEL_API_BASE)

    if isinstance(data, dict):
        return data.get("hotels", [])

    return []


@tool
def search_hotel(
    city: str,
    checkIn: Optional[str] = None,
    checkOut: Optional[str] = None,
) -> List[dict]:
    """
    Search for hotels by city and optional check-in/check-out dates.

    Args:
        city: Hotel city name. Example: Bangkok, Colombo, Singapore.
        checkIn: Optional check-in date in YYYY-MM-DD format.
        checkOut: Optional check-out date in YYYY-MM-DD format.
    """
    params = {"city": city}

    if checkIn:
        params["checkIn"] = checkIn

    if checkOut:
        params["checkOut"] = checkOut

    data = _fetch_json(f"{HOTEL_API_BASE}/search", params=params)

    if isinstance(data, dict):
        return data.get("hotels", [])

    return []


@tool
def book_hotel(
    hotel_id: str,
    guest_name: str,
    guest_email: str,
    check_in_date: str,
    check_out_date: str,
    room_type: str,
) -> dict:
    """Book a hotel room.

    Args:
        hotel_id: ID of the hotel to book
        guest_name: Full name of the guest
        guest_email: Email of the guest
        check_in_date: Check-in date (YYYY-MM-DD)
        check_out_date: Check-out date (YYYY-MM-DD)
        room_type: Type of room (single, double, suite)
    """
    payload = {
        "hotelId": hotel_id,
        "guestName": guest_name,
        "guestEmail": guest_email,
        "checkInDate": check_in_date,
        "checkOutDate": check_out_date,
        "roomType": room_type,
    }
    response = requests.post(f"{HOTEL_API_BASE}/book", json=payload)
    return response.json()

@tool
def get_flights() -> List[dict]:
    """
    Get a list of all available flights.
    Use this when the user asks to show/list all flights.
    """
    data = _fetch_json(FLIGHT_API_BASE)

    if isinstance(data, dict):
        return data.get("flights", [])

    return []


@tool
def search_flights(
    origin: str,
    destination: str,
    date: Optional[str] = None,
) -> List[dict]:
    """
    Search for flights by origin, destination, and optional travel date.

    Args:
        origin: Flight origin city or airport code. Example: CMB, Bangkok.
        destination: Flight destination city or airport code. Example: BKK, Singapore.
        date: Optional flight date in YYYY-MM-DD format.
    """

    if origin and len(origin) == 3 and origin.isalpha():
        normalized_origin = origin.upper()
    else:
        normalized_origin = origin

    if destination and len(destination) == 3 and destination.isalpha():
        normalized_destination = destination.upper()
    else:
        normalized_destination = destination

    params = {
        "origin": normalized_origin,
        "destination": normalized_destination,
    }

    if date:
        params["date"] = date

    data = _fetch_json(f"{FLIGHT_API_BASE}/search", params=params)

    if isinstance(data, dict):
        return data.get("flights", [])

    return []

@tool
def book_flight(flight_id: str, passenger_name: str, passenger_email: str) -> dict:
    """Book a flight ticket.

    Args:
        flight_id: ID of the flight to book
        passenger_name: Full name of the passenger
        passenger_email: Email of the passenger
    """
    payload = {
        "flightId": flight_id,
        "passengerName": passenger_name,
        "passengerEmail": passenger_email,
    }
    response = requests.post(f"{FLIGHT_API_BASE}/book", json=payload)
    return response.json()