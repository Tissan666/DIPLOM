"""PyTorch neural model for suspicious review classification."""

from __future__ import annotations

from copy import deepcopy
from statistics import mean

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class ReviewClassifier(nn.Module):
    """A compact multilayer perceptron over text and numeric review features."""

    def __init__(self, input_dim: int, hidden_dims: list[int] | None = None, dropout: float = 0.25) -> None:
        super().__init__()
        hidden_dims = hidden_dims or [512, 128]

        layers: list[nn.Module] = []
        current_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend(
                [
                    nn.Linear(current_dim, hidden_dim),
                    nn.BatchNorm1d(hidden_dim),
                    nn.GELU(),
                    nn.Dropout(dropout),
                ]
            )
            current_dim = hidden_dim

        layers.append(nn.Linear(current_dim, 1))
        self.network = nn.Sequential(*layers)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        """Return raw logits for each review vector."""
        return self.network(inputs).squeeze(1)


def train_classifier(
    model: ReviewClassifier,
    train_matrix: np.ndarray,
    train_labels: np.ndarray,
    epochs: int = 12,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    val_matrix: np.ndarray | None = None,
    val_labels: np.ndarray | None = None,
    pos_weight: float | None = None,
    patience: int = 4,
) -> dict:
    """Train the PyTorch classifier with optional validation and early stopping."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    dataset = TensorDataset(
        torch.tensor(train_matrix, dtype=torch.float32),
        torch.tensor(train_labels, dtype=torch.float32),
    )
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    if pos_weight is None:
        loss_function = nn.BCEWithLogitsLoss()
    else:
        loss_function = nn.BCEWithLogitsLoss(
            pos_weight=torch.tensor([pos_weight], dtype=torch.float32, device=device)
        )
    history: dict[str, list[float | None]] = {"train_loss": [], "val_loss": []}
    best_state = deepcopy(model.state_dict())
    best_val_loss = float("inf")
    epochs_without_improvement = 0

    model.train()
    for _ in range(epochs):
        epoch_losses: list[float] = []
        for batch_inputs, batch_labels in dataloader:
            batch_inputs = batch_inputs.to(device)
            batch_labels = batch_labels.to(device)

            optimizer.zero_grad()
            logits = model(batch_inputs)
            loss = loss_function(logits, batch_labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            epoch_losses.append(float(loss.item()))

        history["train_loss"].append(mean(epoch_losses) if epoch_losses else 0.0)

        if val_matrix is None or val_labels is None:
            history["val_loss"].append(None)
            continue

        model.eval()
        with torch.no_grad():
            validation_inputs = torch.tensor(val_matrix, dtype=torch.float32, device=device)
            validation_labels = torch.tensor(val_labels, dtype=torch.float32, device=device)
            validation_logits = model(validation_inputs)
            validation_loss = float(loss_function(validation_logits, validation_labels).item())
        model.train()

        history["val_loss"].append(validation_loss)
        if validation_loss < best_val_loss - 1e-4:
            best_val_loss = validation_loss
            best_state = deepcopy(model.state_dict())
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                break

    model.load_state_dict(best_state)
    return {
        "epochs_ran": len(history["train_loss"]),
        "train_loss": history["train_loss"],
        "val_loss": history["val_loss"],
        "best_val_loss": None if best_val_loss == float("inf") else best_val_loss,
    }


def predict_probabilities(model: ReviewClassifier, feature_matrix: np.ndarray) -> np.ndarray:
    """Return suspicious-review probabilities for a feature matrix."""
    device = next(model.parameters()).device
    model.eval()
    with torch.no_grad():
        inputs = torch.tensor(feature_matrix, dtype=torch.float32, device=device)
        logits = model(inputs)
        probabilities = torch.sigmoid(logits)
    return probabilities.detach().cpu().numpy()
