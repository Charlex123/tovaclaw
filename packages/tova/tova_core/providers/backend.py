"""
Abstract backend interface.

Implement this class to connect Tova to your backend API.
All write operations (creating orders, booking appointments, processing payments)
go through this interface.
"""

from abc import ABC, abstractmethod


class BaseBackend(ABC):
    """Backend API provider — handles all write operations and external API calls.

    Implement this class with your own API endpoints. Each method corresponds
    to a capability that the AI agent can use.

    Required methods (core):
        - search_products: Search your product catalog
        - create_order: Create an order
        - execute_order: Execute/fulfill an order
        - cancel_order: Cancel an order
        - check_balance: Check user's payment balance
        - process_payment: Process a payment

    Optional methods (extend for richer features):
        - search_services: Search for services (lab tests, etc.)
        - search_practitioners: Search doctors/nurses
        - book_appointment: Book an appointment
        - cancel_appointment: Cancel an appointment
        - calculate_delivery_fee: Calculate shipping/delivery cost
        - verify_identity: ID verification (e.g., NIN, SSN)
        - validate_prescription: OCR/validate prescription documents
        - get_insurance_providers: List insurance providers
        - link_insurance: Link user's insurance
        - check_insurance: Check user's insurance status
        - check_insurance_coverage: Check coverage for a service
        - process_insurance_payment: Process insurance payment
        - send_emergency_notification: Send emergency alerts
    """

    def __init__(self, auth_token: str | None = None):
        self.auth_token = auth_token

    # ── Required: Product Search & Orders ─────────────────────

    @abstractmethod
    async def search_products(
        self,
        query: str,
        latitude: float = 0,
        longitude: float = 0,
        **kwargs,
    ) -> list[dict]:
        """Search your product catalog (medicines, devices, supplies, etc.).

        Returns a list of dicts, each containing at minimum:
            - id: Product ID
            - name: Product name
            - price: Price per unit
            - in_stock: Whether available
            - store_name: Store/pharmacy name (optional)
            - latitude/longitude: Store location (optional, for proximity)
            - prescription_required: Whether prescription needed (optional)
        """
        ...

    @abstractmethod
    async def create_order(self, data: dict) -> dict:
        """Create a new order.

        Args:
            data: Order details including:
                - request_type: Type of order (e.g., "medical_items", "lab_tests")
                - item_id: Product/service ID
                - item_name: Name
                - quantity: Amount
                - delivery_address: Where to deliver
                - scheduled_date: When to deliver (ISO 8601)
                - cost: Total cost
                - schedule_type: "once" or "recurring"
                - frequency: For recurring (e.g., "daily", "weekly", "monthly")
                - duration: How long recurring lasts
                - Any additional fields your backend needs

        Returns:
            Dict with at minimum: {"id": "order_id", "success": True}
        """
        ...

    @abstractmethod
    async def execute_order(self, order_id: str) -> dict:
        """Execute/fulfill an existing order.

        Returns: {"success": True/False, "message": "..."}
        """
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str, reason: str = "") -> dict:
        """Cancel an order.

        Returns: {"success": True/False, "message": "..."}
        """
        ...

    # ── Required: Payments ────────────────────────────────────

    @abstractmethod
    async def check_balance(self, user_id: str) -> dict:
        """Check user's payment balance/wallet.

        Returns: {"balance": float, "currency": "USD"}
        """
        ...

    @abstractmethod
    async def process_payment(self, data: dict) -> dict:
        """Process a payment for an order or appointment.

        Returns: {"success": True/False, "transaction_id": "..."}
        """
        ...

    # ── Optional: Service Search ──────────────────────────────

    async def search_services(
        self,
        query: str,
        latitude: float = 0,
        longitude: float = 0,
        **kwargs,
    ) -> list[dict]:
        """Search for services (lab tests, diagnostics, etc.).

        Returns list of dicts with: id, name, price, provider_name, etc.
        """
        raise NotImplementedError("Service search not configured")

    # ── Optional: Practitioner Search & Appointments ──────────

    async def search_practitioners(
        self,
        practitioner_type: str = "doctor",
        specialty: str = "",
        query: str = "",
        latitude: float = 0,
        longitude: float = 0,
        **kwargs,
    ) -> list[dict]:
        """Search for healthcare practitioners (doctors, nurses, etc.).

        Returns list of dicts with:
            - schedule_id, professional_id, name, specialty
            - available_slots: [{slot_id, date, start_time, end_time, amount}]
            - rating, avatar, etc.
        """
        raise NotImplementedError("Practitioner search not configured")

    async def book_appointment(self, data: dict) -> dict:
        """Book an appointment with a practitioner.

        Args:
            data: Appointment details (schedule_id, slot_id, professional_id, etc.)

        Returns: {"success": True, "appointment_id": "..."}
        """
        raise NotImplementedError("Appointment booking not configured")

    async def cancel_appointment(self, appointment_id: str, reason: str = "") -> dict:
        """Cancel an appointment.

        Returns: {"success": True/False, "message": "..."}
        """
        raise NotImplementedError("Appointment cancellation not configured")

    # ── Optional: Delivery ────────────────────────────────────

    async def calculate_delivery_fee(self, data: dict) -> dict:
        """Calculate delivery/logistics fee.

        Returns: {"fee": float, "currency": "USD"}
        """
        raise NotImplementedError("Delivery fee calculation not configured")

    # ── Optional: Identity Verification ───────────────────────

    async def verify_identity(self, data: dict) -> dict:
        """Verify user identity (NIN, SSN, passport, etc.).

        Returns: {"verified": True/False, "message": "..."}
        """
        raise NotImplementedError("Identity verification not configured")

    # ── Optional: Prescription ────────────────────────────────

    async def validate_prescription(self, file_url: str) -> dict:
        """Validate a prescription document (OCR + validation).

        Returns: {"valid": True/False, "prescription_url": "...", "message": "..."}
        """
        raise NotImplementedError("Prescription validation not configured")

    # ── Optional: Insurance ───────────────────────────────────

    async def get_insurance_providers(self, **kwargs) -> list[dict]:
        """List available insurance/HMO providers.

        Returns list of dicts with: id, name, description, etc.
        """
        raise NotImplementedError("Insurance providers not configured")

    async def link_insurance(self, data: dict) -> dict:
        """Link user's insurance to their account.

        Returns: {"success": True, "insurance_id": "...", "message": "..."}
        """
        raise NotImplementedError("Insurance linking not configured")

    async def check_insurance(self, user_id: str) -> dict:
        """Check if user has linked insurance.

        Returns: {"has_insurance": True/False, "insurance_list": [...]}
        """
        raise NotImplementedError("Insurance check not configured")

    async def check_insurance_coverage(self, insurance_id: str, service_type: str, amount: float) -> dict:
        """Check insurance coverage for a service.

        Returns: {"covered": True/False, "covered_amount": float, "copay": float}
        """
        raise NotImplementedError("Insurance coverage check not configured")

    async def process_insurance_payment(self, data: dict) -> dict:
        """Process payment through insurance.

        Returns: {"success": True/False, "message": "..."}
        """
        raise NotImplementedError("Insurance payment not configured")

    # ── Optional: Emergency ───────────────────────────────────

    async def send_emergency_notification(self, data: dict) -> dict:
        """Send emergency notification (e.g., nurse home visit safety alert).

        Returns: {"sent": True/False}
        """
        raise NotImplementedError("Emergency notifications not configured")

    # ── Lifecycle ─────────────────────────────────────────────

    async def close(self):
        """Clean up resources (HTTP clients, connections, etc.)."""
        pass
