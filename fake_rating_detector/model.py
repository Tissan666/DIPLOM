"""PyTorch Autoencoder model and helper functions for anomaly detection."""

from __future__ import annotations

from statistics import mean

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class RatingsAutoencoder(nn.Module):
    """Simple feed-forward Autoencoder for learning normal rating behavior patterns."""

    def __init__(self, input_dim: int, hidden_dims: list[int] | None = None) -> None:
        super().__init__()
        hidden_dims = hidden_dims or [64, 32, 16]

        encoder_layers: list[nn.Module] = []
        current_dim = input_dim
        for hidden_dim in hidden_dims:
            encoder_layers.extend([nn.Linear(current_dim, hidden_dim), nn.ReLU()])
            current_dim = hidden_dim

        decoder_layers: list[nn.Module] = []
        reversed_dims = list(reversed(hidden_dims[:-1])) + [input_dim]
        current_dim = hidden_dims[-1]
        for index, hidden_dim in enumerate(reversed_dims):
            decoder_layers.append(nn.Linear(current_dim, hidden_dim))
            if index < len(reversed_dims) - 1:
                decoder_layers.append(nn.ReLU())
            current_dim = hidden_dim

        self.encoder = nn.Sequential(*encoder_layers)
        self.decoder = nn.Sequential(*decoder_layers)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        """Encode and then reconstruct a batch of numerical feature vectors."""
        latent_representation = self.encoder(inputs)
        return self.decoder(latent_representation)


def train_autoencoder(
    model: RatingsAutoencoder,
    train_matrix: np.ndarray,
    epochs: int = 35,
    batch_size: int = 64,
    learning_rate: float = 1e-3,
) -> list[float]:
    """Train the Autoencoder on mostly normal behavior and return epoch losses."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    tensor_data = torch.tensor(train_matrix, dtype=torch.float32)
    dataset = TensorDataset(tensor_data)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_function = nn.MSELoss()
    history: list[float] = []

    model.train()
    for _ in range(epochs):
        epoch_losses: list[float] = []
        for (batch_inputs,) in dataloader:
            batch_inputs = batch_inputs.to(device)

            optimizer.zero_grad()
            reconstructed = model(batch_inputs)
            loss = loss_function(reconstructed, batch_inputs)
            loss.backward()
            optimizer.step()

            epoch_losses.append(float(loss.item()))

        history.append(mean(epoch_losses) if epoch_losses else 0.0)

    return history


def reconstruction_errors(model: RatingsAutoencoder, matrix: np.ndarray) -> np.ndarray:
    """Compute mean squared reconstruction error for each sample."""
    device = next(model.parameters()).device
    model.eval()

    with torch.no_grad():
        inputs = torch.tensor(matrix, dtype=torch.float32, device=device)
        outputs = model(inputs)
        errors = torch.mean((outputs - inputs) ** 2, dim=1)

    return errors.detach().cpu().numpy()
