# gpt4ish_moe_tiny.py
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

# ---------------------------
# Utilities: RMSNorm + RoPE
# ---------------------------

class RMSNorm(nn.Module):
    def __init__(self, d_model: int, eps: float = 1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(d_model))
        self.eps = eps

    def forward(self, x):
        # x: [B, T, D]
        norm = x.pow(2).mean(dim=-1, keepdim=True)
        x = x * torch.rsqrt(norm + self.eps)
        return self.weight * x


def rotate_half(x):
    # split last dim into two halves and rotate
    x1, x2 = x.chunk(2, dim=-1)
    return torch.cat([-x2, x1], dim=-1)


def apply_rope(q, k, cos, sin):
    # q,k: [B, nH, T, Dh], cos,sin: [1, 1, T, Dh]
    q_ = (q * cos) + (rotate_half(q) * sin)
    k_ = (k * cos) + (rotate_half(k) * sin)
    return q_, k_


class RotaryEmbedding(nn.Module):
    # Simple RoPE cache for a given max length
    def __init__(self, dim: int, max_position: int = 4096, base: float = 10000.0):
        super().__init__()
        assert dim % 2 == 0, "RoPE dim must be even"
        inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2).float() / dim))
        t = torch.arange(max_position).float()
        freqs = torch.einsum("t,d->td", t, inv_freq)  # [T, dim/2]
        emb = torch.cat((freqs, freqs), dim=-1)       # [T, dim]
        self.register_buffer("cos", emb.cos()[None, None, :, :], persistent=False)
        self.register_buffer("sin", emb.sin()[None, None, :, :], persistent=False)

    def forward(self, x, seq_len=None):
        # Return cos, sin slices for sequence length
        T = x.size(-2) if seq_len is None else seq_len
        return self.cos[:, :, :T, :], self.sin[:, :, :T, :]

# ---------------------------
# Attention (causal, with RoPE)
# ---------------------------

class CausalSelfAttention(nn.Module):
    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.0, rope_dim: int = None):
        super().__init__()
        assert d_model % n_heads == 0
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head = d_model // n_heads

        self.qkv = nn.Linear(d_model, 3 * d_model, bias=False)
        self.o = nn.Linear(d_model, d_model, bias=False)
        self.attn_dropout = nn.Dropout(dropout)
        self.proj_dropout = nn.Dropout(dropout)

        self.rope_dim = rope_dim or self.d_head
        self.rope = RotaryEmbedding(self.rope_dim)

    def forward(self, x, attn_mask=None):
        B, T, D = x.shape
        qkv = self.qkv(x)  # [B, T, 3D]
        q, k, v = qkv.split(self.d_model, dim=-1)

        # shape to heads
        q = q.view(B, T, self.n_heads, self.d_head).transpose(1, 2)  # [B, H, T, Dh]
        k = k.view(B, T, self.n_heads, self.d_head).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.d_head).transpose(1, 2)

        # apply RoPE to the first rope_dim of q,k
        if self.rope_dim < self.d_head:
            q_ro, q_rest = q[..., :self.rope_dim], q[..., self.rope_dim:]
            k_ro, k_rest = k[..., :self.rope_dim], k[..., self.rope_dim:]
            cos, sin = self.rope(q_ro, seq_len=T)
            q_ro, k_ro = apply_rope(q_ro, k_ro, cos, sin)
            q = torch.cat([q_ro, q_rest], dim=-1)
            k = torch.cat([k_ro, k_rest], dim=-1)
        else:
            cos, sin = self.rope(q, seq_len=T)
            q, k = apply_rope(q, k, cos, sin)

        # scaled dot-product attention with causal mask
        att = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_head)  # [B, H, T, T]

        # causal mask: no looking forward
        causal = torch.ones(T, T, device=x.device, dtype=torch.bool).tril()
        att = att.masked_fill(~causal, float("-inf"))

        if attn_mask is not None:
            att = att + attn_mask  # optional extra masks

        att = F.softmax(att, dim=-1)
        att = self.attn_dropout(att)
        y = torch.matmul(att, v)  # [B, H, T, Dh]

        y = y.transpose(1, 2).contiguous().view(B, T, D)
        y = self.proj_dropout(self.o(y))
        return y

# ---------------------------
# Dense FFN: SwiGLU variant
# ---------------------------

class SwiGLU(nn.Module):
    def __init__(self, d_model: int, d_ff: int):
        super().__init__()
        self.w1 = nn.Linear(d_model, d_ff, bias=False)
        self.w2 = nn.Linear(d_model, d_ff, bias=False)
        self.w3 = nn.Linear(d_ff, d_model, bias=False)

    def forward(self, x):
        return self.w3(F.silu(self.w1(x)) * self.w2(x))

# ---------------------------
# MoE FFN: top-2 routing + capacity
# ---------------------------

class Expert(nn.Module):
    def __init__(self, d_model: int, d_ff: int):
        super().__init__()
        self.ffn = SwiGLU(d_model, d_ff)

    def forward(self, x):
        return self.ffn(x)


class Top2Router(nn.Module):
    def __init__(self, d_model: int, n_experts: int, jitter_noise: float = 1e-2):
        super().__init__()
        self.gate = nn.Linear(d_model, n_experts, bias=False)
        self.jitter = jitter_noise

    def forward(self, x):
        # x: [B, T, D] -> [N, D]
        N, D = x.shape[0] * x.shape[1], x.shape[2]
        x_flat = x.view(N, D)
        logits = self.gate(x_flat)

        if self.jitter > 0 and self.training:
            logits = logits + self.jitter * torch.randn_like(logits)

        probs = F.softmax(logits, dim=-1)                  # [N, E]
        gate_top2, idx_top2 = probs.topk(k=2, dim=-1)      # [N, 2], [N, 2]
        return idx_top2, gate_top2, x_flat


class MoE(nn.Module):
    """
    Top-2 MoE FFN with:
      - capacity factor (tokens per expert cap)
      - load-balance loss (importance + load per expert)
    This is a readable sketch, not a distributed/optimized kernel.
    """
    def __init__(self, d_model: int, d_ff: int, n_experts: int, capacity_factor: float = 1.25, lb_coef: float = 1e-2):
        super().__init__()
        self.n_experts = n_experts
        self.experts = nn.ModuleList([Expert(d_model, d_ff) for _ in range(n_experts)])
        self.router = Top2Router(d_model, n_experts)
        self.capacity_factor = capacity_factor
        self.lb_coef = lb_coef

    def forward(self, x):
        B, T, D = x.shape
        N = B * T

        idx_top2, gate_top2, x_flat = self.router(x)  # [N,2], [N,2], [N,D]
        e1, e2 = idx_top2[:, 0], idx_top2[:, 1]
        g1, g2 = gate_top2[:, 0], gate_top2[:, 1]

        # Capacity per expert (rounded up)
        capacity = math.ceil(self.capacity_factor * (N / self.n_experts))

        # Build token lists per expert for path1 and path2 with capacity truncation
        # Assign path1 first, then spill to path2 if over capacity
        y_flat = x_flat.new_zeros(N, D)
        dispatch_counts = torch.zeros(self.n_experts, dtype=torch.int32, device=x.device)

        # Track importance (sum of gates) and load (count of tokens) for lb loss
        importance = torch.zeros(self.n_experts, device=x.device)
        load = torch.zeros(self.n_experts, device=x.device)

        # First pass: primary expert (path1)
        for e in range(self.n_experts):
            mask = (e1 == e)
            idx = torch.nonzero(mask, as_tuple=False).squeeze(-1)
            if idx.numel() == 0:
                continue
            take = min(capacity, idx.numel())
            chosen = idx[:take]
            x_e = x_flat[chosen]
            out_e = self.experts[e](x_e)
            y_flat[chosen] += out_e * g1[chosen].unsqueeze(-1)

            dispatch_counts[e] += take
            importance[e] += g1[mask].sum()
            load[e] += take

        # Second pass: secondary expert (path2) if capacity remains
        for e in range(self.n_experts):
            remain = max(0, capacity - int(dispatch_counts[e].item()))
            if remain == 0:
                continue
            mask = (e2 == e)
            idx = torch.nonzero(mask, as_tuple=False).squeeze(-1)
            if idx.numel() == 0:
                continue
            take = min(remain, idx.numel())
            chosen = idx[:take]
            x_e = x_flat[chosen]
            out_e = self.experts[e](x_e)
            y_flat[chosen] += out_e * g2[chosen].unsqueeze(-1)

            importance[e] += g2[mask].sum()
            load[e] += take

        y = y_flat.view(B, T, D)

        # Load-balancing loss (Switch/Google style): encourage uniform importance & load
        imp = importance / (importance.sum() + 1e-9)
        ld = load / (load.sum() + 1e-9)
        lb_loss = (imp * ld).sum() * self.lb_coef * self.n_experts  # scaled

        return y, {"load_balance_loss": lb_loss}

# ---------------------------
# Decoder Block (GPT-style)
# ---------------------------

class DecoderBlock(nn.Module):
    def __init__(self, d_model: int, n_heads: int, d_ff: int, dropout: float, use_moe: bool, n_experts: int = 0):
        super().__init__()
        self.ln1 = RMSNorm(d_model)
        self.attn = CausalSelfAttention(d_model, n_heads, dropout=dropout, rope_dim=d_model // n_heads)
        self.ln2 = RMSNorm(d_model)

        self.use_moe = use_moe
        if use_moe:
            assert n_experts > 0
            self.ff = MoE(d_model, d_ff, n_experts=n_experts)
        else:
            self.ff = SwiGLU(d_model, d_ff)

        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        # Attention
        x = x + self.drop(self.attn(self.ln1(x)))
        # FFN (dense or MoE)
        if self.use_moe:
            y, aux = self.ff(self.ln2(x))
            x = x + self.drop(y)
            return x, aux
        else:
            x = x + self.drop(self.ff(self.ln2(x)))
            return x, {}

# ---------------------------
# Tiny GPT-like Model
# ---------------------------

class TinyGPTMoE(nn.Module):
    """
    A small decoder-only stack mixing dense and MoE FFNs.
    Configure which layers use MoE via moe_layers (e.g., {2, 5, 8}).
    """
    def __init__(
        self,
        vocab_size: int = 32000,
        d_model: int = 512,
        n_layers: int = 12,
        n_heads: int = 8,
        d_ff: int = 4 * 512,
        dropout: float = 0.0,
        moe_layers = (2, 5, 8),
        n_experts: int = 16,
        max_seq_len: int = 2048,
    ):
        super().__init__()
        self.max_seq_len = max_seq_len
        self.tok_emb = nn.Embedding(vocab_size, d_model)
        self.drop = nn.Dropout(dropout)

        blocks = []
        for i in range(n_layers):
            use_moe = (i in set(moe_layers))
            blocks.append(DecoderBlock(d_model, n_heads, d_ff, dropout, use_moe, n_experts if use_moe else 0))
        self.blocks = nn.ModuleList(blocks)

        self.ln_f = RMSNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size, bias=False)

    def forward(self, idx, targets=None):
        """
        idx: [B, T] int tokens
        returns:
          logits: [B, T, V]
          loss: cross-entropy (if targets given)
          aux: dict of auxiliary losses (e.g., load-balance)
        """
        B, T = idx.shape
        assert T <= self.max_seq_len, "sequence too long"

        x = self.drop(self.tok_emb(idx))  # [B, T, D]

        aux_losses = 0.0
        for blk in self.blocks:
            x, aux = blk(x)
            if "load_balance_loss" in aux:
                aux_losses = aux_losses + aux["load_balance_loss"]

        x = self.ln_f(x)
        logits = self.head(x)

        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1), ignore_index=-100)
            if aux_losses != 0.0:
                loss = loss + aux_losses

        return logits, loss, {"aux_losses": aux_losses}


# ---------------------------
# Tiny sanity run
# ---------------------------
if __name__ == "__main__":
    torch.manual_seed(0)
    model = TinyGPTMoE(
        vocab_size=32000, d_model=384, n_layers=6, n_heads=6,
        d_ff=1536, dropout=0.0, moe_layers=(1, 3, 5), n_experts=8, max_seq_len=256
    )
    B, T = 2, 64
    x = torch.randint(0, 32000, (B, T))
    y = torch.randint(0, 32000, (B, T))
    logits, loss, aux = model(x, y)
    print("logits:", logits.shape, "loss:", float(loss), "aux:", aux)
