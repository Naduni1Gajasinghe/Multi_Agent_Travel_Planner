import json
import urllib.request
import urllib.parse
from typing import Optional
from mcp.server.fastmcp import FastMCP
import os


mcp = FastMCP("Hotel Service", host="0.0.0.0", port=int(os.environ.get("PORT", 8001)))



BASE_URL = "https://standing-fish-574.convex.site"


def _get_json(url: str):
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except Exception as e:
        return {"error": True, "message": str(e), "url": url}


def _post_json(url: str, payload: dict):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        return {"error": True, "message": str(e), "url": url}


def _unwrap(data):
    if isinstance(data, dict) and "hotels" in data:
        return data["hotels"]
    if isinstance(data, list):
        return data
    return data


@mcp.tool()
def get_all_hotels() -> list[dict] | dict:
    """Retrieve all hotels with full details (id, name, city, price, availability)."""
    return _unwrap(_get_json(f"{BASE_URL}/hotels"))


@mcp.tool()
def search_hotels(city: str, checkIn: Optional[str] = None, checkOut: Optional[str] = None) -> list[dict] | dict:
    """Search hotels by city and optional check-in/check-out dates. Returns full hotel details."""
    params = {"city": city}
    if checkIn:
        params["checkIn"] = checkIn
    if checkOut:
        params["checkOut"] = checkOut
    query_string = urllib.parse.urlencode(params)
    return _unwrap(_get_json(f"{BASE_URL}/hotels/search?{query_string}"))


@mcp.tool()
def book_hotel(hotel_id: str, guest_name: str, guest_email: str,
               check_in_date: str, check_out_date: str, room_type: str) -> dict:
    """Book a hotel room given hotel_id, guest details, dates, and room type."""
    payload = {
        "hotelId": hotel_id,
        "guestName": guest_name,
        "guestEmail": guest_email,
        "checkInDate": check_in_date,
        "checkOutDate": check_out_date,
        "roomType": room_type,
    }
    return _post_json(f"{BASE_URL}/hotels/book", payload)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")