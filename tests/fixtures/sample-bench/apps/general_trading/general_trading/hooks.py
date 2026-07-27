# Fixture hooks.py for the sample bench used by unit tests.
app_name = "general_trading"
app_title = "General Trading"

doc_events = {
    "Sales Invoice": {
        "validate": "general_trading.temp_reservation.service.validate_reservation",
    }
}
