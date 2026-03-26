"""
Nostra Health — Reference implementation of Tova providers.

This shows how Nostra Health connects Tova to their:
- Firestore database (reads)
- Node.js backend API (writes)
- Firebase Auth (JWT verification)
- FCM push notifications
"""

import os
from tova_core.app import create_app
from nostra_backend import NostraBackend
from nostra_store import NostraFirestoreStore
from nostra_auth import NostraAuth
from nostra_notifier import NostraNotifier

# Custom system prompt with Nigeria-specific details
NOSTRA_SYSTEM_PROMPT = """You are Tova, an intelligent AI health assistant for Nostra Health —
a healthcare platform in Nigeria.

[Your full Nostra-specific prompt here — includes:
- Nigerian Naira (NGN, ₦) currency
- NIN verification for nurse bookings
- HMO insurance (Hygeia, AXA Mansard, etc.)
- Country vs. foreign doctors
- Nigerian healthcare context
- Nostra AI Tools references]
"""

# Create providers
store = NostraFirestoreStore()
auth = NostraAuth(jwt_secret=os.environ.get("JWT_SECRET", ""))
notifier = NostraNotifier()

# Create app
app = create_app(
    backend_factory=lambda token: NostraBackend(auth_token=token),
    store=store,
    auth=auth,
    notifier=notifier,
    system_prompt=NOSTRA_SYSTEM_PROMPT,
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
