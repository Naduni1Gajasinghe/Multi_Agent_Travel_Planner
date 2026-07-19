import json
from typing import Optional, Literal

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .mcp_tools import get_mcp_tools
from .llm import llm
from .prompts import get_system_prompt_for_unknown_node, get_system_prompt_with_history
from .entity import GraphState


class TravelExtraction(BaseModel):
    intent: Literal["hotel", "flight", "unknown"] = Field(
        default="unknown",
        description="Main user intent: hotel, flight, or unknown."
    )

    sub_action: Literal["search", "list_all", "book", "general"] = Field(
        default="general",
        description="Action type: search, list_all, book or general."
    )

    city: Optional[str] = Field(
        default=None,
        description="Hotel city name. Example: Mumbai, Colombo, Bangkok."
    )

    check_in: Optional[str] = Field(
        default=None,
        description="Hotel check-in date in YYYY-MM-DD format. Null if not provided."
    )

    check_out: Optional[str] = Field(
        default=None,
        description="Hotel check-out date in YYYY-MM-DD format. Null if not provided."
    )

    origin: Optional[str] = Field(
        default=None,
        description="Flight origin city or airport code. Example: BOM, CMB, Mumbai."
    )

    destination: Optional[str] = Field(
        default=None,
        description="Flight destination city or airport code. Example: DEL, BKK, Delhi."
    )

    flight_date: Optional[str] = Field(
        default=None,
        description="Flight date in YYYY-MM-DD format. Null if not provided."
    )

    hotel_id: Optional[str] = Field(
        default=None,
        description="ID of the hotel to book. Null if not provided."
    )

    guest_name: Optional[str] = Field(
        default=None,
        description="Guest full name for hotel booking. Null if not provided."
    )

    guest_email: Optional[str] = Field(
        default=None,
        description="Guest email for hotel booking. Null if not provided."
    )

    room_type: Optional[str] = Field(
        default=None,
        description="Hotel room type such as single, double, or suite. Null if not provided."
    )

    flight_id: Optional[str] = Field(
        default=None,
        description="ID of the flight to book. Null if not provided."
    )

    passenger_name: Optional[str] = Field(
        default=None,
        description="Passenger full name for flight booking. Null if not provided."
    )

    passenger_email: Optional[str] = Field(
        default=None,
        description="Passenger email for flight booking. Null if not provided."
    )


travel_extractor = llm.with_structured_output(TravelExtraction)


def _parse_mcp_result(result):
    """MCP tools (via langchain-mcp-adapters) return a list of content blocks like
    {"type": "text", "text": "<json string>"}. Unwrap those into plain dicts.
    Also handles the case where a tool already returns a plain dict/list."""
    if isinstance(result, dict):
        if "hotels" in result:
            return result["hotels"]
        if "flights" in result:
            return result["flights"]
        return []

    if isinstance(result, list):
        parsed = []
        for item in result:
            if isinstance(item, dict) and item.get("type") == "text" and "text" in item:
                try:
                    parsed.append(json.loads(item["text"]))
                except (json.JSONDecodeError, TypeError):
                    continue
            elif isinstance(item, dict):
                parsed.append(item)
        return parsed

    return []


def router(state: GraphState) -> dict:
    user_message = state["messages"][-1]
    history_messages = state["messages"][:-1]

    system_prompt = get_system_prompt_with_history("\n".join(history_messages))

    invocation_messages = [SystemMessage(content=system_prompt)]
    for i in range(0, len(history_messages), 2):
        invocation_messages.append(HumanMessage(content=history_messages[i]))
        if i + 1 < len(history_messages):
            invocation_messages.append(AIMessage(content=history_messages[i + 1]))
    invocation_messages.append(HumanMessage(content=user_message))

    try:
        extracted = travel_extractor.invoke(invocation_messages)
        data = extracted.dict()

    except Exception:
        data = {
            "intent": "unknown",
            "sub_action": "general",
            "city": None,
            "check_in": None,
            "check_out": None,
            "origin": None,
            "destination": None,
            "flight_date": None,
            "hotel_id": None,
            "guest_name": None,
            "guest_email": None,
            "room_type": None,
            "flight_id": None,
            "passenger_name": None,
            "passenger_email": None,
        }

    return {
        "intent": data.get("intent", "unknown"),
        "sub_action": data.get("sub_action", "general"),

        "city": data.get("city"),
        "check_in": data.get("check_in"),
        "check_out": data.get("check_out"),

        "origin": data.get("origin"),
        "destination": data.get("destination"),
        "flight_date": data.get("flight_date"),

        "hotel_id": data.get("hotel_id"),
        "guest_name": data.get("guest_name"),
        "guest_email": data.get("guest_email"),
        "room_type": data.get("room_type"),

        "flight_id": data.get("flight_id"),
        "passenger_name": data.get("passenger_name"),
        "passenger_email": data.get("passenger_email"),

        "hotel_results": [],
        "flight_results": [],
        "response_text": "",
    }


def _format_hotel(hotel: dict) -> str:
    name = hotel.get("name", "Unknown hotel")

    city_data = hotel.get("city", "unknown city")
    if isinstance(city_data, dict):
        city = city_data.get("name", "unknown city")
    else:
        city = city_data

    stars = hotel.get("stars", hotel.get("rating", hotel.get("starRating", "N/A")))
    price = hotel.get("price", hotel.get("pricePerNight", "N/A"))
    currency = hotel.get("currency", "USD")

    available = hotel.get(
        "available_rooms",
        hotel.get("availableRooms", hotel.get("available", "N/A"))
    )

    return (
        f"{name} in {city}, "
        f"{stars} stars - {currency} {price}/night - "
        f"{available} rooms"
    )


def _format_flight(flight: dict) -> str:
    airline = flight.get("airline", "Unknown airline")

    number = flight.get(
        "flightNumber",
        flight.get("flight_number", flight.get("flightNo", "N/A"))
    )

    origin_data = flight.get("origin", "unknown")
    destination_data = flight.get("destination", "unknown")

    if isinstance(origin_data, dict):
        origin = origin_data.get("airport", origin_data.get("city", "unknown"))
    else:
        origin = origin_data

    if isinstance(destination_data, dict):
        destination = destination_data.get("airport", destination_data.get("city", "unknown"))
    else:
        destination = destination_data

    flight_date = flight.get(
        "flightDate",
        flight.get("date", flight.get("departure_date", "unknown"))
    )

    departure_time = flight.get(
        "departureTime",
        flight.get("departure_time", "N/A")
    )

    arrival_time = flight.get(
        "arrivalTime",
        flight.get("arrival_time", "N/A")
    )

    price = flight.get("price", "N/A")
    currency = flight.get("currency", "USD")

    seats = flight.get(
        "availableSeats",
        flight.get("available_seats", flight.get("seats", "N/A"))
    )

    return (
        f"{airline} {number} from {origin} to {destination} "
        f"on {flight_date}, {departure_time} - {arrival_time} "
        f"- {currency} {price} - {seats} seats"
    )


async def hotel_node(state: GraphState) -> dict:
    try:
        tools = await get_mcp_tools()
    except Exception as e:
        return {
            "hotel_results": [], "flight_results": [],
            "response_text": f"Hotel service is currently unavailable ({e}). Please try again shortly.",
        }

    get_all_hotels = tools.get("get_all_hotels")
    search_hotels = tools.get("search_hotels")
    book_hotel = tools.get("book_hotel")

    city = state.get("city")
    check_in = state.get("check_in")
    check_out = state.get("check_out")

    if state.get("sub_action") == "book":
        hotel_id = state.get("hotel_id")
        guest_name = state.get("guest_name")
        guest_email = state.get("guest_email")
        room_type = state.get("room_type")

        missing = [f for f, v in [
            ("hotel_id", hotel_id), ("guest_name", guest_name), ("guest_email", guest_email),
            ("check_in", check_in), ("check_out", check_out), ("room_type", room_type),
        ] if not v]

        if missing:
            return {
                "hotel_results": [], "flight_results": [],
                "response_text": "I need more details to book the hotel: hotel_id, guest_name, guest_email, room_type, check_in, and check_out.",
            }

        try:
            result = await book_hotel.ainvoke({
                "hotel_id": hotel_id, "guest_name": guest_name, "guest_email": guest_email,
                "check_in_date": check_in, "check_out_date": check_out, "room_type": room_type,
            })
        except Exception as e:
            return {"hotel_results": [], "flight_results": [], "response_text": f"Booking failed: {e}"}

        parsed = _parse_mcp_result(result if isinstance(result, list) else [result]) if not isinstance(result, dict) else result
        if isinstance(parsed, dict):
            confirmation = parsed.get("message") or parsed.get("status") or "Hotel booking completed."
        elif isinstance(parsed, list) and parsed:
            first = parsed[0]
            confirmation = first.get("message") or first.get("status") or "Hotel booking completed." if isinstance(first, dict) else "Hotel booking completed."
        else:
            confirmation = "Hotel booking completed."

        return {"hotel_results": [], "flight_results": [], "response_text": confirmation}

    try:
        if city:
            params = {"city": city}
            if check_in:
                params["checkIn"] = check_in
            if check_out:
                params["checkOut"] = check_out
            result = await search_hotels.ainvoke(params)
        else:
            result = await get_all_hotels.ainvoke({})
    except Exception as e:
        return {"hotel_results": [], "flight_results": [], "response_text": f"Couldn't reach hotel service: {e}"}

    hotel_results = _parse_mcp_result(result)

    if not hotel_results:
        return {
            "hotel_results": [], "flight_results": [],
            "response_text": "I couldn't find any hotels. Try searching by city, for example: 'available hotels in Mumbai'.",
        }

    return {"hotel_results": hotel_results, "flight_results": [], "response_text": ""}


async def flight_node(state: GraphState) -> dict:
    try:
        tools = await get_mcp_tools()
    except Exception as e:
        return {
            "hotel_results": [], "flight_results": [],
            "response_text": f"Flight service is currently unavailable ({e}). Please try again shortly.",
        }

    get_all_flights = tools.get("get_all_flights")
    search_flights = tools.get("search_flights")
    book_flight = tools.get("book_flight")

    origin = state.get("origin")
    destination = state.get("destination")
    flight_date = state.get("flight_date")

    if state.get("sub_action") == "book":
        flight_id = state.get("flight_id")
        passenger_name = state.get("passenger_name")
        passenger_email = state.get("passenger_email")

        missing = [f for f, v in [
            ("flight_id", flight_id), ("passenger_name", passenger_name), ("passenger_email", passenger_email),
        ] if not v]

        if missing:
            return {
                "hotel_results": [], "flight_results": [],
                "response_text": "I need more details to book the flight: flight_id, passenger_name, and passenger_email.",
            }

        try:
            result = await book_flight.ainvoke({
                "flight_id": flight_id, "passenger_name": passenger_name, "passenger_email": passenger_email,
            })
        except Exception as e:
            return {"hotel_results": [], "flight_results": [], "response_text": f"Booking failed: {e}"}

        parsed = _parse_mcp_result(result if isinstance(result, list) else [result]) if not isinstance(result, dict) else result
        if isinstance(parsed, dict):
            confirmation = parsed.get("message") or parsed.get("status") or "Flight booking completed."
        elif isinstance(parsed, list) and parsed:
            first = parsed[0]
            confirmation = first.get("message") or first.get("status") or "Flight booking completed." if isinstance(first, dict) else "Flight booking completed."
        else:
            confirmation = "Flight booking completed."

        return {"hotel_results": [], "flight_results": [], "response_text": confirmation}

    if origin and not destination or destination and not origin:
        return {
            "hotel_results": [], "flight_results": [],
            "response_text": "I need both departure and destination information. For example: 'flight from BOM to DEL'.",
        }

    try:
        if origin and destination:
            params = {"origin": origin, "destination": destination}
            if flight_date:
                params["date"] = flight_date
            result = await search_flights.ainvoke(params)
        else:
            result = await get_all_flights.ainvoke({})
    except Exception as e:
        return {"hotel_results": [], "flight_results": [], "response_text": f"Couldn't reach flight service: {e}"}

    flight_results = _parse_mcp_result(result)

    if not flight_results:
        return {
            "hotel_results": [], "flight_results": [],
            "response_text": "I couldn't find flights matching your request. Try another route or ask for all flights.",
        }

    return {"hotel_results": [], "flight_results": flight_results, "response_text": ""}


def unknown_node(state: GraphState) -> dict:
    user_message = state["messages"][-1]
    history_messages = state["messages"][:-1]

    system_prompt = get_system_prompt_for_unknown_node("\n".join(history_messages))

    invocation_messages = [SystemMessage(content=system_prompt)]
    for i in range(0, len(history_messages), 2):
        invocation_messages.append(HumanMessage(content=history_messages[i]))
        if i + 1 < len(history_messages):
            invocation_messages.append(AIMessage(content=history_messages[i + 1]))
    invocation_messages.append(HumanMessage(content=user_message))

    try:
        response = llm.invoke(invocation_messages)

        return {
            "hotel_results": [],
            "flight_results": [],
            "response_text": response.content,
        }

    except Exception as e:
        return {
            "hotel_results": [],
            "flight_results": [],
            "response_text": f"I couldn't understand your request clearly. Error: {str(e)}",
        }


def generate_response(state: GraphState) -> dict:
    if state.get("response_text"):
        return {
            "response_text": state["response_text"]
        }

    hotel_results = state.get("hotel_results", [])
    flight_results = state.get("flight_results", [])

    if hotel_results:
        count = len(hotel_results)
        lines = [_format_hotel(hotel) for hotel in hotel_results[:5]]

        return {
            "response_text": (
                f"I found {count} hotel option{'s' if count != 1 else ''}:\n"
                + "\n".join(lines)
            )
        }

    if flight_results:
        count = len(flight_results)
        lines = [_format_flight(flight) for flight in flight_results[:5]]

        return {
            "response_text": (
                f"I found {count} flight option{'s' if count != 1 else ''}:\n"
                + "\n".join(lines)
            )
        }

    return {
        "response_text": "I couldn't find matching travel options."
    }


def route_after_extraction(state: GraphState) -> str:
    intent = state.get("intent", "unknown")

    if intent == "hotel":
        return "hotel"

    if intent == "flight":
        return "flight"

    return "unknown"