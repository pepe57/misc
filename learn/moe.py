import torch
import torch.nn as nn
import torch.nn.functional as F

# ----- Simple Expert: a standard FFN -----
class Expert(nn.Module):
    def __init__(self, d_model, d_hidden):
        super().__init__()
        self.fc1 = nn.Linear(d_model, d_hidden)
        self.fc2 = nn.Linear(d_hidden, d_model)

    def forward(self, x):
        # x: [N_tokens_in_expert, d_model]
        return self.fc2(F.gelu(self.fc1(x)))


# ----- Top-1 Router -----
class Top1Router(nn.Module):
    def __init__(self, d_model, n_experts, temperature=1.0):
        super().__init__()
        self.gate = nn.Linear(d_model, n_experts)
        self.temperature = temperature

    def forward(self, x):
        """
        x: [B, T, d_model]
        returns:
          expert_idx: [B*T] long tensor of chosen expert per token
          gate_scores: [B*T] probability mass of the chosen expert
        """
        B, T, D = x.shape
        x_flat = x.reshape(B*T, D)
        logits = self.gate(x_flat) / self.temperature              # [N, E]
        probs = F.softmax(logits, dim=-1)                          # [N, E]
        gate_vals, expert_idx = probs.max(dim=-1)                  # top-1
        return expert_idx, gate_vals, x_flat


# ----- MoE Layer (top-1) -----
class MoE(nn.Module):
    def __init__(self, d_model, d_hidden, n_experts):
        super().__init__()
        self.n_experts = n_experts
        self.experts = nn.ModuleList([Expert(d_model, d_hidden) for _ in range(n_experts)])
        self.router = Top1Router(d_model, n_experts)

        # Optional: tiny load-balance loss coefficient
        self.balance_loss_coef = 1e-2

    def load_balance_loss(self, expert_idx, n_tokens):
        # Encourage uniform use of experts
        with torch.no_grad():
            counts = torch.bincount(expert_idx, minlength=self.n_experts).float()  # [E]
            frac = counts / float(n_tokens)                                        # usage fraction per expert
        # L2 distance to uniform
        target = torch.full_like(frac, 1.0 / self.n_experts)
        return (frac - target).pow(2).mean()

    def forward(self, x):
        """
        x: [B, T, d_model]
        returns:
          y: [B, T, d_model]
          aux: dict with optional losses/diagnostics
        """
        B, T, D = x.shape
        N = B * T
        import xdev
        xdev.embed()
        expert_idx, gate_vals, x_flat = self.router(x)

        # Allocate output buffer
        y_flat = torch.zeros_like(x_flat)

        # Dispatch to experts (naive per-expert loop for clarity)
        for e in range(self.n_experts):
            mask = (expert_idx == e)
            print(f'Expert {e}: {mask.sum()}')
            if mask.any():
                tokens_e = x_flat[mask]                  # [N_e, D]
                out_e = self.experts[e](tokens_e)        # [N_e, D]
                print(f'out_e.shape={out_e.shape}')
                # Weight by gate prob (scalar per token)
                y_flat[mask] = out_e * gate_vals[mask].unsqueeze(-1)

        y = y_flat.view(B, T, D)

        aux = {
            "load_balance_loss": self.balance_loss_coef * self.load_balance_loss(expert_idx, N)
        }
        return y, aux


# ----- Transformer Block with MoE instead of FFN -----
class TransformerBlockMoE(nn.Module):
    def __init__(self, d_model=768, n_heads=12, d_hidden=3072, n_experts=16, dropout=0.0):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.dropout1 = nn.Dropout(dropout)

        self.ln2 = nn.LayerNorm(d_model)
        self.moe = MoE(d_model, d_hidden, n_experts)
        self.dropout2 = nn.Dropout(dropout)

    def forward(self, x, attn_mask=None, key_padding_mask=None):
        # x: [B, T, d_model]
        # --- Self-Attention ---
        xa = self.ln1(x)
        attn_out, _ = self.attn(xa, xa, xa, attn_mask=attn_mask, key_padding_mask=key_padding_mask)
        x = x + self.dropout1(attn_out)

        # --- MoE (replacing dense FFN) ---
        xm = self.ln2(x)
        moe_out, aux = self.moe(xm)                  # aux has load balance loss, etc.
        x = x + self.dropout2(moe_out)
        return x, aux


# ----- Tiny usage example -----
if __name__ == "__main__":
    torch.manual_seed(0)
    B, T, D = 2, 8, 64
    x = torch.randn(B, T, D)

    block = TransformerBlockMoE(d_model=D, n_heads=4, d_hidden=4*D, n_experts=8)
    y, aux = block(x)         # y: [B, T, D]
    loss = y.pow(2).mean() + aux["load_balance_loss"]  # example regularization usage
    loss.backward()
    print(y.shape, aux)
