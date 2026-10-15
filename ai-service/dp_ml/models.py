import torch
import torch.nn as nn


class RiskNet(nn.Module):
    # GRU risk model. Input: log1p window (batch, 14, n_feat). Normalization is inside.
    def __init__(self, n_feat, mean=None, std=None, hidden=32, dropout=0.2):
        super().__init__()
        mean = torch.zeros(n_feat) if mean is None else torch.as_tensor(mean, dtype=torch.float32)
        std = torch.ones(n_feat) if std is None else torch.as_tensor(std, dtype=torch.float32)
        self.register_buffer("mu", mean.clone())
        self.register_buffer("sd", std.clone())
        self.rnn = nn.GRU(n_feat, hidden, batch_first=True)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        x = torch.clamp((x - self.mu) / self.sd, -10.0, 10.0)
        out, _ = self.rnn(x)
        return self.head(self.drop(out[:, -1, :])).squeeze(-1)


class LSTMAE(nn.Module):
    # LSTM autoencoder. score() returns the reconstruction error per window.
    def __init__(self, n_feat, mean=None, std=None, hidden=32, latent=8):
        super().__init__()
        mean = torch.zeros(n_feat) if mean is None else torch.as_tensor(mean, dtype=torch.float32)
        std = torch.ones(n_feat) if std is None else torch.as_tensor(std, dtype=torch.float32)
        self.register_buffer("mu", mean.clone())
        self.register_buffer("sd", std.clone())
        self.enc = nn.LSTM(n_feat, hidden, batch_first=True)
        self.to_latent = nn.Linear(hidden, latent)
        self.from_latent = nn.Linear(latent, hidden)
        self.dec = nn.LSTM(hidden, hidden, batch_first=True)
        self.out = nn.Linear(hidden, n_feat)

    def score(self, x):
        z = torch.clamp((x - self.mu) / self.sd, -10.0, 10.0)
        _, (h, _) = self.enc(z)
        lat = self.to_latent(h[-1])
        seq = self.from_latent(lat).unsqueeze(1).repeat(1, z.shape[1], 1)
        d, _ = self.dec(seq)
        rec = self.out(d)
        return ((rec - z) ** 2).mean(dim=(1, 2))