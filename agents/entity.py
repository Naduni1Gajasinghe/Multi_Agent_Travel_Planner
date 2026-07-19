from typing import List, Optional, TypedDict

class GraphState(TypedDict):
    messages: List[str]

    intent: str
    sub_action: str

    city: Optional[str]
    check_in: Optional[str]
    check_out: Optional[str]

    origin: Optional[str]
    destination: Optional[str]
    flight_date: Optional[str]

    hotel_id: Optional[str]
    guest_name: Optional[str]
    guest_email: Optional[str]
    room_type: Optional[str]

    flight_id: Optional[str]
    passenger_name: Optional[str]
    passenger_email: Optional[str]

    hotel_results: List[dict]
    flight_results: List[dict]

    response_text: str