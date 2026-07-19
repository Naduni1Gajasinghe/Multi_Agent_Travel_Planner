import json
import urllib.request
import urllib.parse
from typing import Optional
from mcp.server.fastmcp import FastMCP
import os

mcp = FastMCP("Flight Service", port=int(os.environ.get("PORT", 8002)))



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
    if isinstance(data, dict) and "flights" in data:
        return data["flights"]
    if isinstance(data, list):
        return data
    return data


@mcp.tool()
def get_all_flights() -> list[dict] | dict:
    """Retrieve all flights with full details (id, airline, times, price, seats)."""
    return _unwrap(_get_json(f"{BASE_URL}/flights"))


@mcp.tool()
def search_flights(origin: str, destination: str, date: Optional[str] = None) -> list[dict] | dict:
    """Search flights by origin/destination and optional date. Returns full flight details."""
    params = {"origin": origin, "destination": destination}
    if date:
        params["date"] = date
    query_string = urllib.parse.urlencode(params)
    return _unwrap(_get_json(f"{BASE_URL}/flights/search?{query_string}"))


@mcp.tool()
def book_flight(flight_id: str, passenger_name: str, passenger_email: str) -> dict:
    """Book a flight given flight_id and passenger details."""
    payload = {
        "flightId": flight_id,
        "passengerName": passenger_name,
        "passengerEmail": passenger_email,
    }
    return _post_json(f"{BASE_URL}/flights/book", payload)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")