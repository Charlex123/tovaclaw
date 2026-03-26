"""
Machine Learning Engine — real ML models for Tova's self-learning pipeline.

Uses scikit-learn + numpy for:
1. Intent Classification — learns to classify user messages into intent categories
2. Anomaly Detection — flags unusual patterns in CCTV, vehicle, emergency data
3. Preference Prediction — predicts user preferences from behavioral features
4. Behavior Clustering — groups similar user interactions for pattern discovery
5. Entity Extraction — ML-based NER using token features (replaces capitalization heuristic)

All models support online/incremental learning — they improve with every interaction
without requiring batch retraining. Models are serialized to SQLite using safe JSON
serialization (no pickle) with HMAC integrity verification.

Security: All serialization uses JSON + numpy array encoding. No pickle/marshal/exec.
This prevents arbitrary code execution from tampered model files.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.ensemble import IsolationForest
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import LabelEncoder

from tova_core.learning.storage import MLModelStore as _SQLiteModelStore, get_model_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Safe serialization helpers — JSON only, no pickle
# ---------------------------------------------------------------------------

def _ndarray_to_list(arr: np.ndarray | None) -> list | None:
    """Convert numpy array to nested Python lists for JSON serialization."""
    if arr is None:
        return None
    return arr.tolist()


def _list_to_ndarray(data: list | None, dtype=np.float64) -> np.ndarray | None:
    """Convert nested Python lists back to numpy array."""
    if data is None:
        return None
    return np.array(data, dtype=dtype)


def _serialize_sgd_state(clf: SGDClassifier) -> dict:
    """Extract fitted state from SGDClassifier as JSON-safe dict.

    Only serializes known numeric arrays — no arbitrary objects.
    """
    state: dict[str, Any] = {
        "params": {
            "loss": clf.loss,
            "penalty": clf.penalty,
            "alpha": clf.alpha,
            "random_state": clf.random_state,
            "warm_start": clf.warm_start,
        },
    }
    if hasattr(clf, "coef_"):
        state["coef_"] = _ndarray_to_list(clf.coef_)
        state["intercept_"] = _ndarray_to_list(clf.intercept_)
        state["classes_"] = _ndarray_to_list(clf.classes_)
        state["t_"] = float(clf.t_) if hasattr(clf, "t_") else 1.0
        state["n_iter_"] = int(clf.n_iter_) if hasattr(clf, "n_iter_") else 0
        state["is_fitted"] = True
    else:
        state["is_fitted"] = False
    return state


def _restore_sgd_state(state: dict) -> SGDClassifier:
    """Reconstruct SGDClassifier from JSON-safe state dict."""
    params = state.get("params", {})
    clf = SGDClassifier(
        loss=params.get("loss", "modified_huber"),
        penalty=params.get("penalty", "l2"),
        alpha=params.get("alpha", 1e-4),
        random_state=params.get("random_state", 42),
        warm_start=params.get("warm_start", True),
    )
    if state.get("is_fitted"):
        clf.coef_ = _list_to_ndarray(state["coef_"])
        clf.intercept_ = _list_to_ndarray(state["intercept_"])
        clf.classes_ = _list_to_ndarray(state["classes_"], dtype=np.intp)
        if "t_" in state:
            clf.t_ = float(state["t_"])
        if "n_iter_" in state:
            clf.n_iter_ = int(state["n_iter_"])
    return clf


class IntentClassifier:
    """Online intent classifier — learns user intent categories incrementally.

    Uses HashingVectorizer (stateless, no vocabulary to maintain) + SGDClassifier
    (supports partial_fit for online learning). Every time the user sends a message,
    we can classify the intent AND feed the actual intent back for continuous improvement.

    Categories include: question, command, feedback, correction, greeting,
    scheduling, search, creation, update, deletion, monitoring, alert, etc.
    """

    DEFAULT_INTENTS = [
        "question", "command", "feedback", "correction", "greeting",
        "scheduling", "search", "creation", "update", "deletion",
        "monitoring", "alert", "training", "preference", "chitchat",
    ]

    def __init__(self):
        self.vectorizer = HashingVectorizer(
            n_features=2**14,
            alternate_sign=False,
            ngram_range=(1, 2),
            stop_words="english",
        )
        self.label_encoder = LabelEncoder()
        self.label_encoder.fit(self.DEFAULT_INTENTS)
        self.classifier = SGDClassifier(
            loss="modified_huber",
            penalty="l2",
            alpha=1e-4,
            random_state=42,
            warm_start=True,
        )
        self._is_fitted = False
        self._seen_classes: set[str] = set(self.DEFAULT_INTENTS)

    def predict(self, message: str) -> dict[str, Any]:
        if not self._is_fitted:
            return {"intent": "unknown", "confidence": 0.0, "all_scores": {}}

        X = self.vectorizer.transform([message])
        try:
            probs = self.classifier.predict_proba(X)[0]
            classes = self.classifier.classes_
            decoded = self.label_encoder.inverse_transform(classes)
            scores = {label: float(prob) for label, prob in zip(decoded, probs)}
            best_idx = np.argmax(probs)
            return {
                "intent": decoded[best_idx],
                "confidence": float(probs[best_idx]),
                "all_scores": scores,
            }
        except Exception as e:
            logger.debug(f"Intent prediction failed: {e}")
            return {"intent": "unknown", "confidence": 0.0, "all_scores": {}}

    def learn(self, message: str, intent: str) -> None:
        if intent not in self._seen_classes:
            self._seen_classes.add(intent)
            self.label_encoder = LabelEncoder()
            self.label_encoder.fit(sorted(self._seen_classes))

        X = self.vectorizer.transform([message])
        y = self.label_encoder.transform([intent])
        all_classes = self.label_encoder.transform(sorted(self._seen_classes))

        try:
            self.classifier.partial_fit(X, y, classes=all_classes)
            self._is_fitted = True
        except Exception as e:
            logger.debug(f"Intent learning failed: {e}")

    def serialize(self) -> str:
        """Serialize to JSON — no pickle."""
        state = {
            "classifier": _serialize_sgd_state(self.classifier),
            "seen_classes": sorted(self._seen_classes),
            "is_fitted": self._is_fitted,
        }
        return json.dumps(state)

    @classmethod
    def deserialize(cls, data: str) -> "IntentClassifier":
        instance = cls()
        try:
            state = json.loads(data)
            instance.classifier = _restore_sgd_state(state["classifier"])
            instance._seen_classes = set(state["seen_classes"])
            instance._is_fitted = state["is_fitted"]
            instance.label_encoder = LabelEncoder()
            instance.label_encoder.fit(sorted(instance._seen_classes))
        except Exception as e:
            logger.warning(f"Failed to deserialize intent classifier: {e}")
        return instance


class AnomalyDetector:
    """Detects anomalies in numerical feature streams.

    Used by CCTV (unusual motion patterns), vehicle tracking (route deviations,
    speed anomalies), emergency system (unusual alert frequency), and general
    user behavior (unusual activity patterns).

    Uses IsolationForest — unsupervised, works with streaming data.
    Serialization stores the data buffer and refits on load (IsolationForest
    internal tree state is not safely serializable without pickle).
    """

    def __init__(self, contamination: float = 0.1, n_estimators: int = 100):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=42,
            warm_start=True,
        )
        self._buffer: list[list[float]] = []
        self._buffer_size = 50
        self._is_fitted = False

    def feed(self, features: list[float]) -> dict[str, Any]:
        self._buffer.append(features)

        if not self._is_fitted:
            if len(self._buffer) >= self._buffer_size:
                self._fit()
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "samples_seen": len(self._buffer),
                "status": "collecting_baseline",
            }

        X = np.array([features])
        try:
            score = self.model.score_samples(X)[0]
            prediction = self.model.predict(X)[0]
            is_anomaly = prediction == -1

            if len(self._buffer) % 100 == 0:
                self._fit()

            return {
                "is_anomaly": is_anomaly,
                "anomaly_score": float(score),
                "samples_seen": len(self._buffer),
            }
        except Exception as e:
            logger.debug(f"Anomaly detection failed: {e}")
            return {"is_anomaly": False, "anomaly_score": 0.0, "samples_seen": len(self._buffer)}

    def _fit(self) -> None:
        try:
            X = np.array(self._buffer[-500:])
            self.model.fit(X)
            self._is_fitted = True
        except Exception as e:
            logger.debug(f"Anomaly detector fit failed: {e}")

    def serialize(self) -> str:
        """Serialize buffer + config as JSON. Model is refit on deserialize."""
        state = {
            "buffer": self._buffer[-500:],
            "is_fitted": self._is_fitted,
            "contamination": self.contamination,
            "n_estimators": self.n_estimators,
        }
        return json.dumps(state)

    @classmethod
    def deserialize(cls, data: str) -> "AnomalyDetector":
        try:
            state = json.loads(data)
            instance = cls(
                contamination=state.get("contamination", 0.1),
                n_estimators=state.get("n_estimators", 100),
            )
            instance._buffer = state.get("buffer", [])
            instance._is_fitted = False
            # Refit from buffer if we had enough data
            if len(instance._buffer) >= instance._buffer_size:
                instance._fit()
            return instance
        except Exception as e:
            logger.warning(f"Failed to deserialize anomaly detector: {e}")
            return cls()


class PreferencePredictor:
    """Predicts user preferences from behavioral feature vectors.

    Uses SGDClassifier for fast online multiclass prediction.
    """

    PREFERENCE_FEATURES = [
        "hour_of_day", "day_of_week", "message_length", "tool_count",
        "is_question", "is_command", "response_length", "conversation_depth",
        "corrections_count", "session_duration",
    ]

    def __init__(self):
        self.classifier = SGDClassifier(
            loss="hinge",
            penalty=None,
            learning_rate="constant",
            eta0=1.0,
            warm_start=True,
            random_state=42,
        )
        self.label_encoder = LabelEncoder()
        self._categories: list[str] = [
            "concise", "detailed", "morning_person", "evening_person",
            "tool_heavy", "conversational", "task_oriented", "exploratory",
        ]
        self.label_encoder.fit(self._categories)
        self._is_fitted = False

    @staticmethod
    def extract_features(
        user_message: str,
        agent_reply: str,
        tools_used: list[str],
        conversation_depth: int = 1,
        corrections_count: int = 0,
    ) -> np.ndarray:
        now = datetime.now(timezone.utc)
        return np.array([[
            now.hour,
            now.weekday(),
            len(user_message) / 100.0,
            len(tools_used),
            1.0 if "?" in user_message else 0.0,
            1.0 if any(w in user_message.lower() for w in ["create", "make", "send", "schedule", "delete", "update"]) else 0.0,
            len(agent_reply) / 100.0,
            conversation_depth,
            corrections_count,
            0.0,
        ]])

    def predict(self, features: np.ndarray) -> dict[str, Any]:
        if not self._is_fitted:
            return {"category": "unknown", "confidence": 0.0}
        try:
            prediction = self.classifier.predict(features)[0]
            label = self.label_encoder.inverse_transform([prediction])[0]
            decision = self.classifier.decision_function(features)[0]
            confidence = float(np.max(np.abs(decision)) / (np.sum(np.abs(decision)) + 1e-8))
            return {"category": label, "confidence": confidence}
        except Exception as e:
            logger.debug(f"Preference prediction failed: {e}")
            return {"category": "unknown", "confidence": 0.0}

    def learn(self, features: np.ndarray, category: str) -> None:
        if category not in self._categories:
            self._categories.append(category)
            self.label_encoder = LabelEncoder()
            self.label_encoder.fit(self._categories)

        y = self.label_encoder.transform([category])
        all_classes = self.label_encoder.transform(self._categories)

        try:
            self.classifier.partial_fit(features, y, classes=all_classes)
            self._is_fitted = True
        except Exception as e:
            logger.debug(f"Preference learning failed: {e}")

    def serialize(self) -> str:
        state = {
            "classifier": _serialize_sgd_state(self.classifier),
            "categories": self._categories,
            "is_fitted": self._is_fitted,
        }
        return json.dumps(state)

    @classmethod
    def deserialize(cls, data: str) -> "PreferencePredictor":
        instance = cls()
        try:
            state = json.loads(data)
            instance.classifier = _restore_sgd_state(state["classifier"])
            instance._categories = state["categories"]
            instance._is_fitted = state["is_fitted"]
            instance.label_encoder = LabelEncoder()
            instance.label_encoder.fit(instance._categories)
        except Exception as e:
            logger.warning(f"Failed to deserialize preference predictor: {e}")
        return instance


class BehaviorClusterer:
    """Clusters user interactions to discover behavioral patterns.

    Uses MiniBatchKMeans for incremental clustering.
    Serialization stores cluster centers + buffer, reconstructs on load.
    """

    def __init__(self, n_clusters: int = 8):
        self.n_clusters = n_clusters
        self.model = MiniBatchKMeans(
            n_clusters=n_clusters,
            random_state=42,
            batch_size=32,
        )
        self._buffer: list[list[float]] = []
        self._is_fitted = False
        self._cluster_labels: dict[int, str] = {}

    def feed(self, features: list[float]) -> dict[str, Any]:
        self._buffer.append(features)

        if not self._is_fitted:
            if len(self._buffer) >= self.model.n_clusters * 3:
                self._fit()
            return {
                "cluster_id": -1,
                "cluster_name": "collecting_data",
                "n_samples": len(self._buffer),
            }

        X = np.array([features])
        try:
            cluster_id = int(self.model.predict(X)[0])
            if len(self._buffer) % 50 == 0:
                self._fit()
            return {
                "cluster_id": cluster_id,
                "cluster_name": self._cluster_labels.get(cluster_id, f"cluster_{cluster_id}"),
                "n_samples": len(self._buffer),
            }
        except Exception as e:
            logger.debug(f"Clustering failed: {e}")
            return {"cluster_id": -1, "cluster_name": "error", "n_samples": len(self._buffer)}

    def _fit(self) -> None:
        try:
            X = np.array(self._buffer[-1000:])
            self.model.partial_fit(X)
            self._is_fitted = True
            self._label_clusters()
        except Exception as e:
            logger.debug(f"Clustering fit failed: {e}")

    def _label_clusters(self) -> None:
        if not self._is_fitted:
            return
        centroids = self.model.cluster_centers_
        for i, centroid in enumerate(centroids):
            if len(centroid) >= 6:
                if centroid[3] > 2:
                    self._cluster_labels[i] = "power_user"
                elif centroid[4] > 0.5:
                    self._cluster_labels[i] = "explorer"
                elif centroid[5] > 0.5:
                    self._cluster_labels[i] = "task_executor"
                elif centroid[2] < 0.3:
                    self._cluster_labels[i] = "quick_tasker"
                elif centroid[7] > 5:
                    self._cluster_labels[i] = "deep_thinker"
                else:
                    self._cluster_labels[i] = f"pattern_{i}"

    def serialize(self) -> str:
        """Serialize cluster centers + buffer as JSON. No pickle."""
        state: dict[str, Any] = {
            "buffer": self._buffer[-1000:],
            "is_fitted": self._is_fitted,
            "cluster_labels": {str(k): v for k, v in self._cluster_labels.items()},
            "n_clusters": self.n_clusters,
        }
        if self._is_fitted and hasattr(self.model, "cluster_centers_"):
            state["cluster_centers_"] = _ndarray_to_list(self.model.cluster_centers_)
        return json.dumps(state)

    @classmethod
    def deserialize(cls, data: str) -> "BehaviorClusterer":
        try:
            state = json.loads(data)
            instance = cls(n_clusters=state.get("n_clusters", 8))
            instance._buffer = state.get("buffer", [])
            instance._cluster_labels = {int(k): v for k, v in state.get("cluster_labels", {}).items()}
            instance._is_fitted = False

            # Restore from cluster centers if available, otherwise refit from buffer
            if state.get("cluster_centers_"):
                centers = _list_to_ndarray(state["cluster_centers_"])
                if centers is not None and len(instance._buffer) >= instance.n_clusters * 3:
                    # Partial fit with buffer to restore internal state
                    instance._fit()
            elif len(instance._buffer) >= instance.n_clusters * 3:
                instance._fit()

            return instance
        except Exception as e:
            logger.warning(f"Failed to deserialize behavior clusterer: {e}")
            return cls()


class MLEntityExtractor:
    """ML-based named entity extraction using token-level features.

    Uses SGDClassifier with hand-crafted features per token.
    """

    LABELS = ["O", "B-PERSON", "I-PERSON", "B-ORG", "I-ORG", "B-PLACE", "I-PLACE", "B-PROJECT", "I-PROJECT"]

    def __init__(self):
        self.vectorizer = HashingVectorizer(
            n_features=2**12,
            alternate_sign=False,
        )
        self.classifier = SGDClassifier(
            loss="modified_huber",
            penalty="l2",
            alpha=1e-4,
            random_state=42,
        )
        self.label_encoder = LabelEncoder()
        self.label_encoder.fit(self.LABELS)
        self._is_fitted = False

    @staticmethod
    def _token_features(tokens: list[str], idx: int) -> str:
        token = tokens[idx]
        features = [
            f"word={token.lower()}",
            f"is_upper={token[0].isupper()}" if token else "is_upper=False",
            f"is_all_upper={token.isupper()}",
            f"is_alpha={token.isalpha()}",
            f"length={min(len(token), 10)}",
            f"suffix2={token[-2:]}" if len(token) > 2 else "suffix2=_",
            f"suffix3={token[-3:]}" if len(token) > 3 else "suffix3=_",
            f"prefix2={token[:2]}" if len(token) > 2 else "prefix2=_",
        ]

        if idx > 0:
            prev = tokens[idx - 1]
            features.extend([
                f"prev={prev.lower()}",
                f"prev_upper={prev[0].isupper()}" if prev else "prev_upper=False",
            ])
        else:
            features.append("BOS")

        if idx < len(tokens) - 1:
            nxt = tokens[idx + 1]
            features.extend([
                f"next={nxt.lower()}",
                f"next_upper={nxt[0].isupper()}" if nxt else "next_upper=False",
            ])
        else:
            features.append("EOS")

        return " ".join(features)

    def predict(self, text: str) -> list[dict]:
        tokens = text.split()
        if not tokens:
            return []

        if not self._is_fitted:
            return self._heuristic_extract(tokens, text)

        feature_strings = [self._token_features(tokens, i) for i in range(len(tokens))]
        X = self.vectorizer.transform(feature_strings)

        try:
            predictions = self.classifier.predict(X)
            labels = self.label_encoder.inverse_transform(predictions)
            return self._labels_to_entities(tokens, labels, text)
        except Exception:
            return self._heuristic_extract(tokens, text)

    def learn(self, text: str, entities: list[dict]) -> None:
        tokens = text.split()
        if not tokens:
            return

        labels = self._entities_to_labels(tokens, text, entities)
        feature_strings = [self._token_features(tokens, i) for i in range(len(tokens))]
        X = self.vectorizer.transform(feature_strings)
        y = self.label_encoder.transform(labels)
        all_classes = self.label_encoder.transform(self.LABELS)

        try:
            self.classifier.partial_fit(X, y, classes=all_classes)
            self._is_fitted = True
        except Exception as e:
            logger.debug(f"Entity learning failed: {e}")

    def _heuristic_extract(self, tokens: list[str], text: str) -> list[dict]:
        entities = []
        skip = {"I", "The", "This", "That", "Yes", "No", "OK", "Please", "Thanks",
                "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
                "January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December",
                "What", "When", "Where", "Who", "How", "Why", "Can", "Could",
                "Would", "Should", "Will", "Do", "Does", "Did", "Is", "Are", "Was", "Were"}
        i = 0
        while i < len(tokens):
            if i == 0 or tokens[i - 1] in [".", "!", "?"]:
                i += 1
                continue
            if tokens[i][0:1].isupper() and tokens[i].isalpha() and len(tokens[i]) > 1:
                name_parts = [tokens[i]]
                j = i + 1
                while j < len(tokens) and tokens[j][0:1].isupper() and tokens[j].isalpha():
                    name_parts.append(tokens[j])
                    j += 1
                name = " ".join(name_parts)
                if name not in skip and len(name) > 1:
                    start = text.find(name)
                    entities.append({
                        "text": name, "type": "ENTITY",
                        "start": start, "end": start + len(name) if start >= 0 else -1,
                    })
                i = j
            else:
                i += 1
        return entities

    def _entities_to_labels(self, tokens: list[str], text: str, entities: list[dict]) -> list[str]:
        labels = ["O"] * len(tokens)
        offsets = []
        pos = 0
        for token in tokens:
            start = text.find(token, pos)
            offsets.append((start, start + len(token)))
            pos = start + len(token)

        for entity in entities:
            ent_start = entity.get("start", -1)
            ent_end = entity.get("end", -1)
            ent_type = entity.get("type", "ENTITY").upper()
            if ent_type not in ["PERSON", "ORG", "PLACE", "PROJECT"]:
                ent_type = "PERSON"
            first = True
            for idx, (tok_start, tok_end) in enumerate(offsets):
                if tok_start >= ent_start and tok_end <= ent_end:
                    prefix = "B" if first else "I"
                    labels[idx] = f"{prefix}-{ent_type}"
                    first = False
        return labels

    def _labels_to_entities(self, tokens: list[str], labels: list[str], text: str) -> list[dict]:
        entities = []
        current_entity: list[str] = []
        current_type = ""

        for token, label in zip(tokens, labels):
            if label.startswith("B-"):
                if current_entity:
                    ent_text = " ".join(current_entity)
                    start = text.find(ent_text)
                    entities.append({
                        "text": ent_text, "type": current_type,
                        "start": start, "end": start + len(ent_text),
                    })
                current_entity = [token]
                current_type = label[2:]
            elif label.startswith("I-") and current_entity:
                current_entity.append(token)
            else:
                if current_entity:
                    ent_text = " ".join(current_entity)
                    start = text.find(ent_text)
                    entities.append({
                        "text": ent_text, "type": current_type,
                        "start": start, "end": start + len(ent_text),
                    })
                    current_entity = []
                    current_type = ""

        if current_entity:
            ent_text = " ".join(current_entity)
            start = text.find(ent_text)
            entities.append({
                "text": ent_text, "type": current_type,
                "start": start, "end": start + len(ent_text),
            })
        return entities

    def serialize(self) -> str:
        """Serialize to JSON — no pickle."""
        state = {
            "classifier": _serialize_sgd_state(self.classifier),
            "is_fitted": self._is_fitted,
        }
        return json.dumps(state)

    @classmethod
    def deserialize(cls, data: str) -> "MLEntityExtractor":
        instance = cls()
        try:
            state = json.loads(data)
            instance.classifier = _restore_sgd_state(state["classifier"])
            instance._is_fitted = state["is_fitted"]
        except Exception as e:
            logger.warning(f"Failed to deserialize entity extractor: {e}")
        return instance


class UserModelStore:
    """Persists and loads per-user ML model states in async SQLite.

    Each user gets their own trained models — so Tova's ML adapts
    individually per user, not globally. All data stored locally,
    no external services required.
    """

    MODEL_KEYS = {
        "intent_classifier": IntentClassifier,
        "anomaly_detector": AnomalyDetector,
        "preference_predictor": PreferencePredictor,
        "behavior_clusterer": BehaviorClusterer,
        "entity_extractor": MLEntityExtractor,
    }

    def __init__(self, db_path: str | None = None):
        self._store = get_model_store(db_path)

    async def save_model(self, user_id: str, model_name: str, model: Any) -> None:
        """Serialize and persist a model for a user."""
        try:
            data = model.serialize()
            await self._store.save(
                user_id=user_id,
                model_name=model_name,
                model_type=type(model).__name__,
                model_data=data,
            )
        except Exception as e:
            logger.debug(f"Failed to save ML model '{model_name}' for user {user_id}: {e}")

    async def load_model(self, user_id: str, model_name: str) -> Any | None:
        """Load a persisted model for a user."""
        model_cls = self.MODEL_KEYS.get(model_name)
        if not model_cls:
            return None

        try:
            row = await self._store.load(user_id, model_name)
            if row:
                return model_cls.deserialize(row["model_data"])
        except Exception as e:
            logger.debug(f"Failed to load ML model '{model_name}' for user {user_id}: {e}")

        return None

    async def load_or_create(self, user_id: str, model_name: str) -> Any:
        """Load a model or create a fresh one if not found."""
        model = await self.load_model(user_id, model_name)
        if model is None:
            model_cls = self.MODEL_KEYS.get(model_name)
            if model_cls:
                model = model_cls()
            else:
                raise ValueError(f"Unknown model: {model_name}")
        return model
