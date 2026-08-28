# Event field and evidence rules

Use these rules when the source email needs more than straightforward field copying.

## Evidence priority

Prefer, in order:

1. A current structured invitation or reservation field
2. The latest authoritative message text
3. The message subject and headers
4. Clearly labeled attachment content exposed by Gmail
5. Contextual inference supported by multiple source clues

Treat forwarded or quoted text, promotional examples, footer office hours, and unrelated dates as weak evidence. A later reschedule or cancellation overrides an earlier message.

## Field mapping

| Calendar field | Source and handling |
|---|---|
| Title | Formal event name or subject. Remove mail prefixes only when they are not part of the name. |
| Start/end | Copy explicit values exactly. Preserve minute precision and AM/PM meaning. |
| Time zone | Use an explicit zone first. Otherwise use a location or invitation zone only when unambiguous; do not silently use the agent's local zone. |
| Location | Physical venue, station pair, hotel address, or other source-stated place. |
| Online meeting | Copy every complete join URL verbatim into the description. Preserve dial-in details when useful. |
| Organizer | Use the invitation organizer or explicitly labeled host, not automatically the visible sender. |
| Attendees | Use explicitly listed participants. Do not infer recipients hidden by mailing lists or forwarding. |
| Notes | Summarize essential participation instructions and retain identifiers needed to recognize the booking later. |

Do not copy secrets unnecessary for using the event, such as payment-card data or account passwords.

## Time interpretation

- Resolve omitted years only from message date, event sequence, and other explicit context. Ask when more than one year is plausible.
- Preserve `10:03 発` and `12:18 着` as `10:03` start and `12:18` end.
- Do not infer an end time from a standard meeting length. Ask before writing when the end is required but unknown.
- Treat an overnight end earlier on the clock than the start as next-day only when the source or itinerary makes that rollover unambiguous.
- Convert to RFC3339 or the app's required representation without changing the represented local time or instant.

## Travel and lodging

- Rail/flight: map departure to start and arrival to end. Retain carrier, service/train/flight number, origin, destination, seat, passenger count, booking reference, and relevant boarding instructions.
- Hotel: map stated check-in to start and check-out to end. Put the property address in location. Retain booking reference, room/plan, check-in constraints, phone, and material access or parking instructions.
- Never replace itinerary times with estimated travel or stay durations.

## Duplicate and conflict assessment

A source message ID, invitation UID, reservation number, or booking reference that already appears in an event is the strongest duplicate signal. Without an identifier, use a combination of:

- same or equivalent title;
- same start and end;
- same venue or route;
- same organizer;
- same meeting URL.

An overlap alone is a conflict, not a duplicate. Search a time range wide enough to catch all-day and overnight events. After an indeterminate create response, perform the same duplicate search before retrying.

## Description shape

Keep the description concise and source-grounded. A useful order is:

1. Join URL(s) and dial-in details
2. Organizer and participation notes
3. Venue, itinerary, or reservation details
4. Source identifiers

Do not paste the entire email unless the user requests it or the full text is necessary to preserve instructions.
