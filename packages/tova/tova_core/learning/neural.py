"""
Neural Pattern Recognizer — lightweight numpy-based neural network.

A small feedforward neural network that learns interaction patterns
without requiring PyTorch or TensorFlow. Runs on CPU with pure numpy.

Architecture:
    Input (N features) → Dense(64, ReLU) → Dense(32, ReLU) → Dense(K outputs, Softmax)

Uses:
1. Interaction pattern recognition — predicts what the user will do next
   based on their recent interaction sequence
2. Tool recommendation — suggests which tools to use based on user intent
3. Response style adaptation — adjusts response characteristics to user behavior
4. Urgency scoring — predicts how urgent/important a message is

Supports online learning with mini-batch SGD and momentum.
"""

from __future__ import annotations

import json
import logging
import base64
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class NeuralLayer:
    """Single dense layer with weights, bias, and activation."""

    def __init__(self, input_dim: int, output_dim: int, activation: str = "relu"):
        # Xavier/Glorot initialization
        scale = np.sqrt(2.0 / (input_dim + output_dim))
        self.weights = np.random.randn(input_dim, output_dim).astype(np.float32) * scale
        self.bias = np.zeros(output_dim, dtype=np.float32)
        self.activation = activation

        # Momentum buffers for SGD
        self._weight_momentum = np.zeros_like(self.weights)
        self._bias_momentum = np.zeros_like(self.bias)

        # Cache for backpropagation
        self._input_cache: np.ndarray | None = None
        self._output_cache: np.ndarray | None = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Forward pass: linear transform + activation."""
        self._input_cache = x
        z = x @ self.weights + self.bias

        if self.activation == "relu":
            out = np.maximum(0, z)
        elif self.activation == "softmax":
            exp_z = np.exp(z - np.max(z, axis=-1, keepdims=True))
            out = exp_z / (np.sum(exp_z, axis=-1, keepdims=True) + 1e-8)
        elif self.activation == "sigmoid":
            out = 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))
        elif self.activation == "tanh":
            out = np.tanh(z)
        else:
            out = z  # linear

        self._output_cache = out
        return out

    def backward(self, grad_output: np.ndarray, learning_rate: float = 0.001, momentum: float = 0.9) -> np.ndarray:
        """Backward pass: compute gradients and update weights."""
        # Activation derivative
        if self.activation == "relu":
            grad = grad_output * (self._output_cache > 0).astype(np.float32)
        elif self.activation == "softmax":
            # For softmax + cross-entropy, gradient is already (predicted - true)
            grad = grad_output
        elif self.activation == "sigmoid":
            grad = grad_output * self._output_cache * (1 - self._output_cache)
        elif self.activation == "tanh":
            grad = grad_output * (1 - self._output_cache ** 2)
        else:
            grad = grad_output

        # Compute parameter gradients
        batch_size = max(self._input_cache.shape[0], 1)
        weight_grad = self._input_cache.T @ grad / batch_size
        bias_grad = np.mean(grad, axis=0)

        # Gradient clipping
        grad_norm = np.linalg.norm(weight_grad)
        if grad_norm > 5.0:
            weight_grad = weight_grad * 5.0 / grad_norm

        # SGD with momentum
        self._weight_momentum = momentum * self._weight_momentum - learning_rate * weight_grad
        self._bias_momentum = momentum * self._bias_momentum - learning_rate * bias_grad

        self.weights += self._weight_momentum
        self.bias += self._bias_momentum

        # Gradient for previous layer
        return grad @ self.weights.T

    def to_dict(self) -> dict:
        return {
            "weights": self.weights.tolist(),
            "bias": self.bias.tolist(),
            "activation": self.activation,
            "weight_momentum": self._weight_momentum.tolist(),
            "bias_momentum": self._bias_momentum.tolist(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NeuralLayer":
        weights = np.array(data["weights"], dtype=np.float32)
        input_dim, output_dim = weights.shape
        layer = cls(input_dim, output_dim, data.get("activation", "relu"))
        layer.weights = weights
        layer.bias = np.array(data["bias"], dtype=np.float32)
        layer._weight_momentum = np.array(data.get("weight_momentum", np.zeros_like(weights)), dtype=np.float32)
        layer._bias_momentum = np.array(data.get("bias_momentum", np.zeros_like(layer.bias)), dtype=np.float32)
        return layer


class NeuralPatternNet:
    """Lightweight feedforward neural network for pattern recognition.

    Architectures:
    - "interaction": Input(10) → 64 → 32 → K (predict next action type)
    - "tool_recommend": Input(10) → 64 → 32 → T (score each available tool)
    - "urgency": Input(10) → 32 → 16 → 1 (urgency score 0-1)
    - "custom": Any architecture via layer_dims parameter

    All architectures support incremental online learning.
    """

    PRESETS = {
        "interaction": {"layer_dims": [10, 64, 32], "output_activation": "softmax"},
        "tool_recommend": {"layer_dims": [10, 64, 32], "output_activation": "softmax"},
        "urgency": {"layer_dims": [10, 32, 16], "output_activation": "sigmoid"},
    }

    def __init__(
        self,
        input_dim: int = 10,
        output_dim: int = 8,
        hidden_dims: list[int] | None = None,
        output_activation: str = "softmax",
        learning_rate: float = 0.001,
        preset: str | None = None,
    ):
        if preset and preset in self.PRESETS:
            config = self.PRESETS[preset]
            hidden_dims = config["layer_dims"]
            output_activation = config["output_activation"]

        dims = hidden_dims or [64, 32]
        self.learning_rate = learning_rate
        self.output_activation = output_activation

        # Build layers
        self.layers: list[NeuralLayer] = []
        prev_dim = input_dim
        for dim in dims:
            self.layers.append(NeuralLayer(prev_dim, dim, activation="relu"))
            prev_dim = dim
        # Output layer
        self.layers.append(NeuralLayer(prev_dim, output_dim, activation=output_activation))

        self._training_steps = 0
        self._loss_history: list[float] = []

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Forward pass through all layers."""
        if x.ndim == 1:
            x = x.reshape(1, -1)
        out = x.astype(np.float32)
        for layer in self.layers:
            out = layer.forward(out)
        return out

    def predict(self, features: np.ndarray) -> dict[str, Any]:
        """Predict from features and return structured result."""
        output = self.forward(features)

        if self.output_activation == "softmax":
            predicted_class = int(np.argmax(output, axis=-1)[0])
            confidence = float(output[0, predicted_class])
            return {
                "class": predicted_class,
                "confidence": confidence,
                "scores": output[0].tolist(),
            }
        elif self.output_activation == "sigmoid":
            score = float(output[0, 0]) if output.shape[-1] == 1 else float(np.mean(output[0]))
            return {"score": score, "raw": output[0].tolist()}
        else:
            return {"output": output[0].tolist()}

    def train_step(self, x: np.ndarray, y_true: np.ndarray) -> float:
        """Single training step with backpropagation.

        Args:
            x: Input features [batch_size, input_dim]
            y_true: Target — one-hot for softmax, float for sigmoid [batch_size, output_dim]

        Returns:
            Loss value for this step
        """
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if y_true.ndim == 1:
            y_true = y_true.reshape(1, -1)

        # Forward pass
        output = self.forward(x)

        # Compute loss
        if self.output_activation == "softmax":
            # Cross-entropy loss
            loss = -np.mean(np.sum(y_true * np.log(output + 1e-8), axis=-1))
            grad = output - y_true
        elif self.output_activation == "sigmoid":
            # Binary cross-entropy
            loss = -np.mean(y_true * np.log(output + 1e-8) + (1 - y_true) * np.log(1 - output + 1e-8))
            grad = output - y_true
        else:
            # MSE
            loss = float(np.mean((output - y_true) ** 2))
            grad = 2 * (output - y_true) / y_true.shape[-1]

        # Backward pass through layers in reverse
        for layer in reversed(self.layers):
            grad = layer.backward(grad, learning_rate=self.learning_rate)

        self._training_steps += 1
        self._loss_history.append(float(loss))
        # Keep last 1000 loss values
        if len(self._loss_history) > 1000:
            self._loss_history = self._loss_history[-1000:]

        return float(loss)

    def train_batch(self, x_batch: np.ndarray, y_batch: np.ndarray, epochs: int = 1) -> float:
        """Train on a batch for multiple epochs."""
        total_loss = 0.0
        for _ in range(epochs):
            total_loss = self.train_step(x_batch, y_batch)
        return total_loss

    def get_stats(self) -> dict:
        """Return training statistics."""
        recent_loss = self._loss_history[-10:] if self._loss_history else []
        return {
            "training_steps": self._training_steps,
            "recent_avg_loss": float(np.mean(recent_loss)) if recent_loss else 0.0,
            "total_params": sum(
                l.weights.size + l.bias.size for l in self.layers
            ),
            "layer_shapes": [
                f"{l.weights.shape[0]}→{l.weights.shape[1]}({l.activation})"
                for l in self.layers
            ],
        }

    def serialize(self) -> str:
        """Serialize the full network state."""
        state = {
            "layers": [l.to_dict() for l in self.layers],
            "learning_rate": self.learning_rate,
            "output_activation": self.output_activation,
            "training_steps": self._training_steps,
            "loss_history": self._loss_history[-100:],
        }
        return json.dumps(state)

    @classmethod
    def deserialize(cls, data: str) -> "NeuralPatternNet":
        """Restore network from serialized state."""
        state = json.loads(data)
        layers_data = state["layers"]

        # Reconstruct dimensions from layer weights
        input_dim = np.array(layers_data[0]["weights"]).shape[0]
        output_dim = np.array(layers_data[-1]["weights"]).shape[1]
        hidden_dims = [np.array(l["weights"]).shape[1] for l in layers_data[:-1]]

        net = cls(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_dims=hidden_dims,
            output_activation=state.get("output_activation", "softmax"),
            learning_rate=state.get("learning_rate", 0.001),
        )

        # Replace layers with deserialized ones
        net.layers = [NeuralLayer.from_dict(l) for l in layers_data]
        net._training_steps = state.get("training_steps", 0)
        net._loss_history = state.get("loss_history", [])

        return net


class InteractionPredictor:
    """Predicts the user's next likely action based on interaction sequence.

    Wraps NeuralPatternNet with domain-specific feature extraction and
    action mapping for Tova's use cases.
    """

    ACTION_MAP = {
        0: "ask_question",
        1: "give_command",
        2: "provide_feedback",
        3: "correct_tova",
        4: "request_report",
        5: "create_something",
        6: "update_something",
        7: "check_status",
    }

    def __init__(self):
        self.net = NeuralPatternNet(
            input_dim=10,
            output_dim=len(self.ACTION_MAP),
            hidden_dims=[64, 32],
            output_activation="softmax",
            learning_rate=0.002,
        )

    def predict_next_action(self, features: np.ndarray) -> dict[str, Any]:
        """Predict the user's next likely action."""
        result = self.net.predict(features)
        action_id = result.get("class", 0)
        return {
            "predicted_action": self.ACTION_MAP.get(action_id, "unknown"),
            "confidence": result.get("confidence", 0.0),
            "all_actions": {
                self.ACTION_MAP[i]: score
                for i, score in enumerate(result.get("scores", []))
                if i in self.ACTION_MAP
            },
        }

    def learn(self, features: np.ndarray, actual_action: str) -> float:
        """Train with the actual action that occurred."""
        reverse_map = {v: k for k, v in self.ACTION_MAP.items()}
        action_id = reverse_map.get(actual_action, 0)
        y = np.zeros(len(self.ACTION_MAP), dtype=np.float32)
        y[action_id] = 1.0
        return self.net.train_step(features, y)

    def serialize(self) -> str:
        return self.net.serialize()

    @classmethod
    def deserialize(cls, data: str) -> "InteractionPredictor":
        instance = cls()
        instance.net = NeuralPatternNet.deserialize(data)
        return instance


class UrgencyScorer:
    """Scores how urgent/important a user message is (0.0 to 1.0).

    Trained on features like: keyword presence (emergency, urgent, ASAP),
    message length, punctuation density, time of day, user history.
    """

    def __init__(self):
        self.net = NeuralPatternNet(
            input_dim=10,
            output_dim=1,
            hidden_dims=[32, 16],
            output_activation="sigmoid",
            learning_rate=0.002,
        )

    @staticmethod
    def extract_features(message: str) -> np.ndarray:
        """Extract urgency-relevant features from a message."""
        msg_lower = message.lower()
        urgency_keywords = ["urgent", "emergency", "asap", "immediately", "critical",
                           "help", "danger", "alert", "now", "hurry"]
        keyword_count = sum(1 for kw in urgency_keywords if kw in msg_lower)

        return np.array([[
            keyword_count / len(urgency_keywords),              # keyword density
            message.count("!") / max(len(message), 1) * 10,   # exclamation density
            1.0 if message.isupper() and len(message) > 5 else 0.0,  # ALL CAPS
            len(message) / 500.0,                               # message length
            1.0 if "?" not in message else 0.0,                 # not a question
            message.count("!!!") * 0.3,                         # extreme punctuation
            1.0 if any(w in msg_lower for w in ["fire", "accident", "injury", "blood"]) else 0.0,
            1.0 if any(w in msg_lower for w in ["please", "when you can", "no rush"]) else 0.0,  # anti-urgency
            keyword_count,                                       # raw keyword count
            0.0,                                                 # placeholder for time context
        ]], dtype=np.float32)

    def score(self, message: str) -> dict[str, Any]:
        """Score the urgency of a message."""
        features = self.extract_features(message)
        result = self.net.predict(features)
        score = result.get("score", 0.0)

        if score > 0.8:
            level = "critical"
        elif score > 0.6:
            level = "high"
        elif score > 0.4:
            level = "medium"
        elif score > 0.2:
            level = "low"
        else:
            level = "routine"

        return {"urgency_score": score, "urgency_level": level}

    def learn(self, message: str, actual_urgency: float) -> float:
        """Train with actual urgency label (0.0 to 1.0)."""
        features = self.extract_features(message)
        y = np.array([[actual_urgency]], dtype=np.float32)
        return self.net.train_step(features, y)

    def serialize(self) -> str:
        return self.net.serialize()

    @classmethod
    def deserialize(cls, data: str) -> "UrgencyScorer":
        instance = cls()
        instance.net = NeuralPatternNet.deserialize(data)
        return instance
