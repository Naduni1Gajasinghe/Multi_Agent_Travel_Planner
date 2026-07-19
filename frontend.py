import json
import os
import requests
import gradio as gr

API_URL = os.environ.get("TRAVEL_PLANNER_API_URL", "http://127.0.0.1:8000/chat")
API_STREAM_URL = os.environ.get(
    "TRAVEL_PLANNER_STREAM_URL",
    API_URL.rsplit("/chat", 1)[0] + "/chat/stream",
)


def format_flights(flights):
    lines = ["**Flights:**"]
    for flight in flights:
        id = flight.get("_id", "Unknown ID")
        airline = flight.get("airline", "Unknown Airline")
        flight_number = flight.get("flightNumber", "Unknown Flight Number")
        origin_data = flight.get("origin")
        destination_data = flight.get("destination")
        origin = origin_data.get("airport", "Unknown Origin") if isinstance(origin_data, dict) else (origin_data or "Unknown Origin")
        destination = destination_data.get("airport", "Unknown Destination") if isinstance(destination_data, dict) else (destination_data or "Unknown Destination")
        flight_date = flight.get("flightDate", "Unknown Date")
        departure_time = flight.get("departureTime", "Unknown Departure Time")
        arrival_time = flight.get("arrivalTime", "Unknown Arrival Time")
        price = flight.get("price", "Unknown Price")
        currency = flight.get("currency", "Unknown Currency")
        available_seats = flight.get("availableSeats", "Unknown Available Seats")
        lines.append(
            f"- `{id}` — {airline} {flight_number}, {origin} → {destination}, "
            f"{flight_date} {departure_time}-{arrival_time}, {currency} {price}, {available_seats} seats"
        )
    return "\n".join(lines)


def format_hotels(hotels):
    lines = ["**Hotels:**"]
    for hotel in hotels:
        id = hotel.get("_id", "Unknown ID")
        name = hotel.get("name") or "Unknown Hotel"
        city = hotel.get("city") or (hotel.get("location") or {}).get("city", "")
        price_per_night = hotel.get("pricePerNight") or "Price not available"
        currency = hotel.get("currency", "")
        lines.append(f"- `{id}` — {name} in {city}, {currency} {price_per_night}/night")
    return "\n".join(lines)


def respond(message, history):
    if history is None:
        history = []
    if not message or not message.strip():
        yield history, history
        return

    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": "_Connecting..._"},
    ]
    yield history, history

    assistant_text = ""
    hotels_md = ""
    flights_md = ""

    try:
        with requests.post(API_STREAM_URL, json={"message": message}, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data: "):
                    continue
                payload = raw_line[len("data: "):]
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                etype = event.get("type")

                if etype == "activity":
                    history[-1]["content"] = f"_{event.get('text', 'Working...')}_"
                    yield history, history

                elif etype == "token":
                    assistant_text += event.get("text", "")
                    history[-1]["content"] = assistant_text
                    yield history, history

                elif etype == "data":
                    if event.get("hotels"):
                        hotels_md = format_hotels(event["hotels"])
                    if event.get("flights"):
                        flights_md = format_flights(event["flights"])

                elif etype == "error":
                    history[-1]["content"] = f"⚠️ {event.get('text', 'Something went wrong.')}"
                    yield history, history
                    return

                elif etype == "done":
                    break

    except requests.exceptions.RequestException as exc:
        history[-1]["content"] = (
            f"⚠️ I couldn't reach the travel planner backend right now ({exc}). "
            "If this is the first request in a while, the server may still be waking up — please try again shortly."
        )
        yield history, history
        return

    parts = [assistant_text] if assistant_text.strip() else []
    if flights_md:
        parts.append(flights_md)
    if hotels_md:
        parts.append(hotels_md)

    history[-1]["content"] = "\n\n".join(parts) if parts else "I couldn't find matching travel options."
    yield history, history


TRAVEL_THEME = gr.themes.Soft(
    primary_hue=gr.themes.colors.teal,
    secondary_hue=gr.themes.colors.orange,
    neutral_hue=gr.themes.colors.slate,
    font=[gr.themes.GoogleFont("Poppins"), "ui-sans-serif", "sans-serif"],
)

CUSTOM_CSS = """
.gradio-container {
    max-width: 900px !important;
    margin: auto !important;
    background: linear-gradient(135deg, #f0fdfa 0%, #fff7ed 100%);
}
#header-block {text-align: center; padding: 8px 0 4px 0;}
#header-block h1 {margin-bottom: 0.2em;}
"""


def main():
    with gr.Blocks(title="TripWeaver — Travel Planner") as demo:
        with gr.Column(elem_id="header-block"):
            gr.Markdown("# ✈️ TripWeaver — Your AI Travel Planner 🏨")
            gr.Markdown(
                "Ask about hotels, flights, or general travel questions — just type naturally, "
                "no need to say which agent to use."
            )

        chatbot = gr.Chatbot(label="Chat", height=460)

        with gr.Row():
            message = gr.Textbox(
                label="Your message",
                placeholder="e.g. Find me hotels in Bangkok, or flights from CMB to BKK on 2026-08-01",
                scale=5,
                autofocus=True,
            )
            submit = gr.Button("Send ✈️", variant="primary", scale=1)

        gr.Examples(
            examples=[
                "Show me all hotels",
                "Find flights from CMB to BKK",
                "What's the best time to visit Bangkok?",
            ],
            inputs=message,
        )

        submit_event = submit.click(respond, inputs=[message, chatbot], outputs=[chatbot, chatbot])
        submit_event.then(lambda: "", None, message)

        message_event = message.submit(respond, inputs=[message, chatbot], outputs=[chatbot, chatbot])
        message_event.then(lambda: "", None, message)

    demo.queue()
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
        theme=TRAVEL_THEME,
        css=CUSTOM_CSS,
    )


if __name__ == "__main__":
    main()