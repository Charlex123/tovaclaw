# Nostra Health Example

This example shows how Nostra Health uses Tova with:
- **Firebase/Firestore** as the data store
- **Node.js backend API** for write operations
- **Firebase Auth (JWT)** for authentication
- **FCM** for push notifications

## Setup

```bash
# Install with Firebase support
pip install "tova[anthropic,firebase]"

# Set environment variables
export ANTHROPIC_API_KEY=sk-ant-...
export FIREBASE_PROJECT_ID=your-project-id
export GOOGLE_APPLICATION_CREDENTIALS=./firebase-service-account.json
export BACKEND_API_URL=http://localhost:3000/api/v1
export JWT_SECRET=your-jwt-secret

# Run
uvicorn main:app --port 8000
```

## Architecture

```
Flutter App → Node.js Backend → Tova (this service) → Node.js Backend (writes)
                                     ↓
                                 Firestore (reads)
```

See `main.py` for the full implementation.
