"""
Self-Learning Engine — Tova trains itself from every interaction.

After each conversation turn, the engine:
1. Extracts facts, preferences, and patterns from the exchange
2. Stores them in the user's Brain Box (per-feature memory)
3. Optionally feeds structured data into RAG datasets for retrieval
4. Tracks what it learned and when, so it can prioritize recent knowledge
5. Trains ML models (intent classifier, behavior clusterer, anomaly detector)
6. Runs neural networks (interaction predictor, urgency scorer)
7. Collects training data for the custom "Tova" model (with user consent)

This makes Tova smarter with every conversation — it never asks the same
thing twice and adapts to each user's style over time.

The learning happens at three time scales:
- **Immediate**: Brain Box memories (this conversation, this user)
- **Session**: ML models adapt in real-time (scikit-learn online learning)
- **Long-term**: Training data accumulates for fine-tuning the Tova model

Usage:
    learner = SelfLearner()

    # After each agent turn:
    await learner.learn_from_turn(
        user_id="user_123",
        user_message="Book a meeting with John tomorrow at 3pm",
        agent_reply="I've scheduled a meeting...",
        tools_used=["create_event"],
        agent_id="agent_456",
        feature="events",
    )
"""

from __future__ import annotations

import json
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

import numpy as np

from tova_core.learning.storage import (
    LearningDB,
    BrainMemoryStore,
    InteractionLog,
    get_learning_db,
    get_brain_store,
    get_interaction_log,
)
from tova_core.learning.ml_engine import (
    IntentClassifier,
    AnomalyDetector,
    PreferencePredictor,
    BehaviorClusterer,
    MLEntityExtractor,
    UserModelStore,
)
from tova_core.learning.neural import (
    InteractionPredictor,
    UrgencyScorer,
)

logger = logging.getLogger(__name__)


# Categories of learnable knowledge
LEARNING_CATEGORIES = {
    "preference": "User preferences (tone, format, time, style)",
    "fact": "Factual information about the user or their context",
    "pattern": "Behavioral patterns (common requests, workflows)",
    "correction": "Things the user corrected or clarified",
    "entity": "Named entities (people, places, projects the user references)",
    "ml_insight": "Machine learning model predictions and classifications",
}

# Map tool usage to intent labels for training the classifier
TOOL_INTENT_MAP = {
    "search_products": "search",
    "create_todo": "creation",
    "create_event": "scheduling",
    "create_note": "creation",
    "send_email": "command",
    "list_emails": "search",
    "report_emergency": "alert",
    "escalate_emergency": "alert",
    "trigger_emergency_call": "alert",
    "list_cameras": "monitoring",
    "get_camera_snapshot": "monitoring",
    "check_for_anomalies": "monitoring",
    "get_vehicle_position": "monitoring",
    "query_dataset": "search",
    "train_with_data": "training",
    "correct_knowledge": "correction",
    "create_agent_for_user": "creation",
}

# Max number of per-user model instances to keep in memory
_MODEL_CACHE_MAX = 64


class _LRUCache(OrderedDict):
    """Bounded LRU cache — evicts least-recently-used entries when full."""

    def __init__(self, maxsize: int = _MODEL_CACHE_MAX):
        super().__init__()
        self._maxsize = maxsize

    def __getitem__(self, key):
        self.move_to_end(key)
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        while len(self) > self._maxsize:
            self.popitem(last=False)

    def get(self, key, default=None):
        if key in self:
            return self[key]
        return default


class SelfLearner:
    """Extracts knowledge from conversations and feeds it back into memory.

    Works at four levels:
    1. SQLite Brain Store: Fast, per-feature key-value memories (always active, local)
    2. RAG Dataset: Deep knowledge storage for complex data (when vector_store available)
    3. ML Models: scikit-learn classifiers + numpy neural nets for pattern recognition
    4. Training Pipeline: Collects data for fine-tuning the custom Tova model

    All learning data is stored locally in SQLite — no external services required.
    ML models are per-user and persist across sessions via SQLite.
    Training data collection requires explicit user consent.
    """

    def __init__(
        self,
        db_path: str | None = None,
        vector_store: Any | None = None,
        embedder: Any | None = None,
        enable_ml: bool = True,
    ):
        self._db = get_learning_db(db_path)
        self._brain = BrainMemoryStore(self._db)
        self._log = InteractionLog(self._db)
        self.vector_store = vector_store
        self.embedder = embedder
        self.enable_ml = enable_ml

        # ML model store — SQLite backed, per-user isolation
        self._model_store = UserModelStore(db_path)

        # Training data collector — consent-gated, anonymized
        self._training_data_gen = None
        try:
            from tova_core.training.data_generator import TrainingDataGenerator
            self._training_data_gen = TrainingDataGenerator(db_path)
        except ImportError:
            logger.debug("Training pipeline not available")

        # LRU-bounded in-memory model caches (per user_id)
        self._intent_classifiers: _LRUCache = _LRUCache()
        self._anomaly_detectors: _LRUCache = _LRUCache()
        self._preference_predictors: _LRUCache = _LRUCache()
        self._behavior_clusterers: _LRUCache = _LRUCache()
        self._entity_extractors: _LRUCache = _LRUCache()
        self._interaction_predictors: _LRUCache = _LRUCache()
        self._urgency_scorers: _LRUCache = _LRUCache()

    async def _get_model(self, user_id: str, model_name: str, cache: _LRUCache, factory):
        """Load a model from cache or store, or create a new one."""
        existing = cache.get(user_id)
        if existing is not None:
            return existing

        if self.enable_ml:
            try:
                model = await self._model_store.load_or_create(user_id, model_name)
            except Exception:
                model = factory()
        else:
            model = factory()

        cache[user_id] = model
        return model

    async def _save_models(self, user_id: str) -> None:
        """Persist all cached models for a user (called periodically, not every turn)."""
        if not self.enable_ml:
            return

        save_map = [
            ("intent_classifier", self._intent_classifiers),
            ("preference_predictor", self._preference_predictors),
            ("behavior_clusterer", self._behavior_clusterers),
            ("entity_extractor", self._entity_extractors),
        ]

        for model_name, cache in save_map:
            model = cache.get(user_id)
            if model is not None:
                try:
                    await self._model_store.save_model(user_id, model_name, model)
                except Exception as e:
                    logger.debug(f"Failed to save {model_name} for {user_id}: {e}")

    async def learn_from_turn(
        self,
        user_id: str,
        user_message: str,
        agent_reply: str,
        tools_used: list[str] | None = None,
        agent_id: str = "",
        feature: str = "general",
        conversation_id: str = "",
    ) -> dict[str, Any]:
        """Extract learnings from a single conversation turn.

        This is called automatically after every agent response.
        Combines heuristic extraction with ML model training/inference.

        Returns:
            {"learned": int, "categories": [...], "details": [...], "ml_insights": {...}}
        """
        learned = []
        ml_insights = {}

        # ── Heuristic Extraction ─────────────────────────────────

        # 1. Extract user preferences from the message
        prefs = self._extract_preferences(user_message, agent_reply, tools_used or [])
        for pref in prefs:
            await self._remember(user_id, feature, pref)
            learned.append(pref)

        # 2. Extract entities (names, places, projects)  — ML-enhanced
        entities = await self._extract_entities_ml(user_id, user_message)
        for entity in entities:
            await self._remember(user_id, feature, entity)
            learned.append(entity)

        # 3. Track tool usage patterns
        if tools_used:
            pattern = await self._track_tool_pattern(user_id, feature, tools_used)
            if pattern:
                learned.append(pattern)

        # 4. Track conversation patterns
        await self._track_interaction(user_id, feature, user_message, tools_used or [])

        # 5. If RAG is available, index the conversation for deep retrieval
        if self.vector_store and self.embedder:
            await self._index_for_rag(
                user_id, user_message, agent_reply,
                tools_used or [], conversation_id,
            )

        # ── ML Model Training & Inference ────────────────────────

        if self.enable_ml:
            try:
                ml_insights = await self._run_ml_pipeline(
                    user_id, user_message, agent_reply, tools_used or [],
                )

                # Store ML insights as brain memories
                if ml_insights.get("intent"):
                    await self._remember(user_id, feature, {
                        "key": "last_intent",
                        "value": json.dumps(ml_insights["intent"]),
                        "category": "ml_insight",
                    })

                if ml_insights.get("urgency", {}).get("urgency_level") in ("critical", "high"):
                    await self._remember(user_id, feature, {
                        "key": "high_urgency_detected",
                        "value": json.dumps(ml_insights["urgency"]),
                        "category": "ml_insight",
                    })

            except Exception as e:
                logger.debug(f"ML pipeline error (non-critical): {e}")

            # Persist models every 10 interactions to avoid excessive writes
            try:
                count_str = await self._log.get_stat(user_id, feature, "interaction_count")
                count = int(count_str) if count_str else 0
                if count % 10 == 0:
                    await self._save_models(user_id)
            except Exception:
                pass

        # ── Training Data Collection (consent-gated) ─────────────
        training_result = {}
        if self._training_data_gen:
            try:
                training_result = await self._training_data_gen.maybe_collect(
                    user_id=user_id,
                    user_message=user_message,
                    agent_reply=agent_reply,
                    tools_used=tools_used or [],
                    thinking=ml_insights.get("reasoning_chain", ""),
                    quality_signals={
                        "task_completed": bool(tools_used),
                        "intent": ml_insights.get("intent", {}).get("intent", ""),
                    },
                )
            except Exception as e:
                logger.debug(f"Training data collection failed (non-critical): {e}")

        if learned:
            logger.debug(
                f"Self-learn: extracted {len(learned)} learnings for user {user_id} "
                f"in feature '{feature}'"
            )

        return {
            "learned": len(learned),
            "categories": list(set(l.get("category", "") for l in learned)),
            "details": learned,
            "ml_insights": ml_insights,
            "training_data": training_result,
        }

    async def _run_ml_pipeline(
        self,
        user_id: str,
        user_message: str,
        agent_reply: str,
        tools_used: list[str],
    ) -> dict[str, Any]:
        """Run all ML models on this interaction: classify, predict, cluster, detect."""
        insights = {}

        # 1. Intent Classification — predict + train
        intent_clf = await self._get_model(
            user_id, "intent_classifier",
            self._intent_classifiers, IntentClassifier,
        )
        intent_result = intent_clf.predict(user_message)
        insights["intent"] = intent_result

        # Train with inferred label from tools used
        inferred_intent = self._infer_intent_from_tools(tools_used, user_message)
        if inferred_intent:
            intent_clf.learn(user_message, inferred_intent)

        # 2. Urgency Scoring — neural network
        if user_id not in self._urgency_scorers:
            self._urgency_scorers[user_id] = UrgencyScorer()
        urgency = self._urgency_scorers[user_id].score(user_message)
        insights["urgency"] = urgency

        # 3. Preference Prediction
        pref_pred = await self._get_model(
            user_id, "preference_predictor",
            self._preference_predictors, PreferencePredictor,
        )
        features = PreferencePredictor.extract_features(
            user_message, agent_reply, tools_used,
        )
        pref_result = pref_pred.predict(features)
        insights["user_behavior"] = pref_result

        # Train preference predictor with inferred category
        inferred_category = self._infer_behavior_category(user_message, tools_used)
        if inferred_category:
            pref_pred.learn(features, inferred_category)

        # 4. Behavior Clustering
        clusterer = await self._get_model(
            user_id, "behavior_clusterer",
            self._behavior_clusterers, BehaviorClusterer,
        )
        feature_list = features[0].tolist()
        cluster_result = clusterer.feed(feature_list)
        insights["cluster"] = cluster_result

        # 5. Interaction Prediction — neural network
        if user_id not in self._interaction_predictors:
            self._interaction_predictors[user_id] = InteractionPredictor()
        predictor = self._interaction_predictors[user_id]
        next_action = predictor.predict_next_action(features)
        insights["predicted_next_action"] = next_action

        # Train with the actual action that just happened
        actual_action = self._infer_action_type(tools_used, user_message)
        if actual_action:
            predictor.learn(features, actual_action)

        # 6. Anomaly Detection
        detector = await self._get_model(
            user_id, "anomaly_detector",
            self._anomaly_detectors, AnomalyDetector,
        )
        anomaly_result = detector.feed(feature_list)
        insights["anomaly"] = anomaly_result

        return insights

    def _infer_intent_from_tools(self, tools_used: list[str], message: str) -> str | None:
        for tool_name in tools_used:
            if tool_name in TOOL_INTENT_MAP:
                return TOOL_INTENT_MAP[tool_name]

        msg_lower = message.lower()
        if "?" in message:
            return "question"
        if any(w in msg_lower for w in ["no,", "wrong", "actually", "not that", "incorrect"]):
            return "correction"
        if any(w in msg_lower for w in ["hello", "hi ", "hey", "good morning"]):
            return "greeting"
        return None

    def _infer_behavior_category(self, message: str, tools_used: list[str]) -> str | None:
        if len(tools_used) > 2:
            return "tool_heavy"
        if "?" in message and len(tools_used) == 0:
            return "conversational"
        if any(w in message.lower() for w in ["create", "make", "send", "schedule", "delete"]):
            return "task_oriented"
        if len(message) < 30:
            return "concise"
        if len(message) > 200:
            return "detailed"
        return None

    def _infer_action_type(self, tools_used: list[str], message: str) -> str | None:
        if "?" in message:
            return "ask_question"
        if any(w in message.lower() for w in ["no,", "wrong", "incorrect"]):
            return "correct_tova"
        if any(w in message.lower() for w in ["create", "make", "add", "new"]):
            return "create_something"
        if any(w in message.lower() for w in ["update", "change", "modify", "edit"]):
            return "update_something"
        if any(w in message.lower() for w in ["status", "check", "how", "where"]):
            return "check_status"
        if tools_used:
            return "give_command"
        return None

    async def _extract_entities_ml(self, user_id: str, message: str) -> list[dict]:
        """Extract entities using ML model (falls back to heuristic if untrained)."""
        if self.enable_ml:
            try:
                extractor = await self._get_model(
                    user_id, "entity_extractor",
                    self._entity_extractors, MLEntityExtractor,
                )
                ml_entities = extractor.predict(message)
                return [
                    {
                        "key": f"entity_{ent['text'].lower().replace(' ', '_')}",
                        "value": f"{ent['text']} ({ent['type']})",
                        "category": "entity",
                    }
                    for ent in ml_entities
                ]
            except Exception as e:
                logger.debug(f"ML entity extraction failed, using heuristic: {e}")

        return self._extract_entities(message)

    async def learn_from_data(
        self,
        user_id: str,
        data: Any,
        data_type: str = "json",
        feature: str = "general",
        dataset_id: str = "",
    ) -> dict[str, Any]:
        """Train Tova with explicit data provided by the user.

        Handles: JSON objects/arrays, key-value pairs, plain text, CSV strings.
        Each piece of data is stored in SQLite (for fast recall)
        and optionally in RAG (for deep retrieval).
        """
        brain_count = 0
        rag_count = 0
        ns = f"brain_{feature}"

        if isinstance(data, dict):
            for key, value in data.items():
                value_str = json.dumps(value, default=str) if not isinstance(value, str) else value
                await self._brain.save(
                    namespace=ns, user_id=user_id, key=key, value=value_str,
                    category="fact", metadata={"source": "user_training", "data_type": data_type},
                )
                brain_count += 1

        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    key = str(item.get("name", item.get("id", item.get("title", f"item_{i}"))))
                    value = json.dumps(item, default=str)
                else:
                    key = f"item_{i}"
                    value = str(item)
                await self._brain.save(
                    namespace=ns, user_id=user_id, key=key, value=value,
                    category="fact", metadata={"source": "user_training", "array_index": i},
                )
                brain_count += 1

        elif isinstance(data, str):
            lines = [l.strip() for l in data.split("\n") if l.strip()]
            for i, line in enumerate(lines):
                for sep in [":", "=", " - "]:
                    if sep in line:
                        parts = line.split(sep, 1)
                        await self._brain.save(
                            namespace=ns, user_id=user_id,
                            key=parts[0].strip(), value=parts[1].strip(),
                            category="fact", metadata={"source": "user_training", "line": i},
                        )
                        brain_count += 1
                        break
                else:
                    await self._brain.save(
                        namespace=ns, user_id=user_id,
                        key=f"knowledge_{i}", value=line,
                        category="fact", metadata={"source": "user_training", "line": i},
                    )
                    brain_count += 1

        # Also feed into RAG if available
        if self.vector_store and self.embedder and dataset_id:
            try:
                from tova_core.rag.ingest import IngestionPipeline
                pipeline = IngestionPipeline(self.vector_store, self.embedder)

                content = json.dumps(data, default=str) if not isinstance(data, str) else data
                result = await pipeline.ingest(
                    content=content,
                    content_type="application/json" if not isinstance(data, str) else "text/plain",
                    collection_name=f"ds_{user_id}_{dataset_id}",
                    source_name=f"training_{feature}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                )
                rag_count = result.get("chunks_created", 0)
            except Exception as e:
                logger.warning(f"RAG ingestion during training failed: {e}")

        return {
            "items_learned": brain_count + rag_count,
            "brain_memories": brain_count,
            "rag_chunks": rag_count,
        }

    async def learn_from_correction(
        self,
        user_id: str,
        feature: str,
        what_was_wrong: str,
        what_is_correct: str,
        user_message: str = "",
    ) -> None:
        """Learn from a user correction — highest priority memory.

        Also generates a preference training pair (rejected vs chosen)
        for DPO fine-tuning of the Tova model.
        """
        await self._brain.save(
            namespace=f"brain_{feature}",
            user_id=user_id,
            key=f"correction_{what_was_wrong[:50].replace(' ', '_')}",
            value=f"WRONG: {what_was_wrong} → CORRECT: {what_is_correct}",
            category="correction",
            relevance_score=1.0,
            metadata={"source": "user_correction", "permanent": True},
        )

        # Collect preference pair for DPO training (corrections are gold-standard signals)
        if self._training_data_gen and user_message:
            try:
                await self._training_data_gen.collect_correction(
                    user_id=user_id,
                    original_response=what_was_wrong,
                    corrected_response=what_is_correct,
                    user_message=user_message,
                )
            except Exception as e:
                logger.debug(f"Training correction collection failed: {e}")

    # ── Private helpers ──────────────────────────────────────────

    async def _remember(self, user_id: str, feature: str, item: dict) -> None:
        """Store a learned item into SQLite brain memory."""
        metadata = item.get("metadata", {"source": "self_learning"})
        relevance = metadata.pop("relevance_score", 1.0) if isinstance(metadata, dict) else 1.0
        await self._brain.save(
            namespace=f"brain_{feature}",
            user_id=user_id,
            key=item.get("key", "unknown"),
            value=item.get("value", ""),
            category=item.get("category", "fact"),
            relevance_score=relevance,
            metadata=metadata,
        )
        await self._log.log_learning(
            user_id=user_id,
            feature=feature,
            category=item.get("category", "fact"),
            key=item.get("key", "unknown"),
            value=item.get("value", ""),
        )

    # ── Private extraction methods ─────────────────────────────

    def _extract_preferences(
        self,
        user_message: str,
        agent_reply: str,
        tools_used: list[str],
    ) -> list[dict]:
        """Extract user preferences from conversation heuristics."""
        prefs = []
        msg_lower = user_message.lower()

        if any(w in msg_lower for w in ["morning", "afternoon", "evening", "night"]):
            for period in ["morning", "afternoon", "evening", "night"]:
                if period in msg_lower:
                    prefs.append({
                        "key": "preferred_time",
                        "value": period,
                        "category": "preference",
                    })
                    break

        if "email" in msg_lower and any(w in msg_lower for w in ["prefer", "rather", "always"]):
            prefs.append({
                "key": "preferred_contact",
                "value": "email",
                "category": "preference",
            })
        elif "call" in msg_lower and any(w in msg_lower for w in ["prefer", "rather", "always"]):
            prefs.append({
                "key": "preferred_contact",
                "value": "phone",
                "category": "preference",
            })

        if "high priority" in msg_lower or "urgent" in msg_lower:
            prefs.append({
                "key": "urgency_tendency",
                "value": "high",
                "category": "preference",
            })

        if any(w in msg_lower for w in ["brief", "short", "concise", "quick"]):
            prefs.append({
                "key": "preferred_response_style",
                "value": "concise",
                "category": "preference",
            })
        elif any(w in msg_lower for w in ["detailed", "explain", "elaborate", "thorough"]):
            prefs.append({
                "key": "preferred_response_style",
                "value": "detailed",
                "category": "preference",
            })

        return prefs

    def _extract_entities(self, message: str) -> list[dict]:
        """Extract named entities from user messages using heuristics."""
        entities = []
        words = message.split()

        i = 0
        while i < len(words):
            if i == 0 or words[i - 1] in [".", "!", "?"]:
                i += 1
                continue

            if words[i][0:1].isupper() and words[i].isalpha() and len(words[i]) > 1:
                name_parts = [words[i]]
                j = i + 1
                while j < len(words) and words[j][0:1].isupper() and words[j].isalpha():
                    name_parts.append(words[j])
                    j += 1

                name = " ".join(name_parts)
                skip = {"I", "The", "This", "That", "Yes", "No", "OK", "Please", "Thanks",
                        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
                        "January", "February", "March", "April", "May", "June", "July",
                        "August", "September", "October", "November", "December"}
                if name not in skip and len(name) > 1:
                    entities.append({
                        "key": f"entity_{name.lower().replace(' ', '_')}",
                        "value": name,
                        "category": "entity",
                    })
                i = j
            else:
                i += 1

        return entities

    async def _track_tool_pattern(
        self,
        user_id: str,
        feature: str,
        tools_used: list[str],
    ) -> dict | None:
        """Track which tools the user triggers most often."""
        tools_str = ", ".join(tools_used)
        ns = f"brain_{feature}"

        memories = await self._brain.load(ns, user_id, category="pattern")
        freq_mem = next(
            (m for m in memories if m.get("key") == "frequent_tools"), None
        )

        if freq_mem:
            existing = freq_mem.get("value", "")
            entries = [e.strip() for e in existing.split("|") if e.strip()]
            entries.append(tools_str)
            entries = entries[-20:]
            new_value = " | ".join(entries)
        else:
            new_value = tools_str

        await self._brain.save(
            namespace=ns, user_id=user_id,
            key="frequent_tools", value=new_value, category="pattern",
        )

        return {"key": "frequent_tools", "value": tools_str, "category": "pattern"}

    async def _track_interaction(
        self,
        user_id: str,
        feature: str,
        user_message: str,
        tools_used: list[str],
    ) -> None:
        """Track interaction count and last active timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        await self._log.increment_stat(user_id, feature, "interaction_count")
        await self._log.set_stat(user_id, feature, "last_active", now)

    async def _index_for_rag(
        self,
        user_id: str,
        user_message: str,
        agent_reply: str,
        tools_used: list[str],
        conversation_id: str,
    ) -> None:
        """Index the conversation turn into a per-user RAG collection for deep retrieval."""
        try:
            from tova_core.rag.ingest import IngestionPipeline
            pipeline = IngestionPipeline(self.vector_store, self.embedder)

            doc = (
                f"User asked: {user_message}\n"
                f"Assistant responded: {agent_reply[:500]}\n"
                f"Tools used: {', '.join(tools_used) if tools_used else 'none'}"
            )

            collection = f"ds_{user_id}_conversation_memory"
            await pipeline.ingest(
                content=doc,
                content_type="text/plain",
                collection_name=collection,
                source_name=f"conv_{conversation_id}_{datetime.now(timezone.utc).strftime('%H%M%S')}",
                metadata={"type": "conversation", "user_id": user_id},
            )
        except Exception as e:
            logger.debug(f"RAG indexing of conversation failed (non-critical): {e}")
