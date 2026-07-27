"""Fixture controller used by unit tests; not a real Frappe app."""


class TemporaryStockReservation:
    def validate(self):
        if getattr(self, "qty", 0) <= 0:
            raise ValueError("Reservation quantity must be positive")
