"""
Needs a lot of cleanup
"""
from __future__ import annotations
import random
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np

from manim import BOLD
from manim import LaggedStart
from manim import Create
from manim import FadeIn, FadeOut
from manim import Circle, Dot
from manim import Arrow
from manim import Rectangle
from manim import Mobject
from manim import Text
from manim import VGroup
from manim import Scene
from manim import (
    BLUE_B,
    BLUE_E,
    GOLD_B,
    GRAY_BROWN,
    GREEN,
    GREEN_B,
    GREEN_E,
    ORANGE,
    PINK,
    PURPLE_B,
    RED,
    RED_B,
    TEAL_B,
    WHITE,
    YELLOW_B,
    YELLOW_D,
    YELLOW_E,
)
from manim import DOWN, LEFT, RIGHT, UP

Circle


# ====================================================================
# Config knobs you can tweak for teaching
# ====================================================================
N_TOKENS = 10  # tokens in the sequence
N_EXPERTS = 6  # number of experts in the MoE block
TOP_K = 2  # top-k routing
CAPACITY_FACTOR = 1.25  # capacity factor (tokens per expert cap ~ CAPACITY_FACTOR * N_TOKENS / N_EXPERTS)
N_LAYERS = 2  # how many blocks to visualize (attention + FFN/MoE)
SEED = 7  # random seed for reproducibility (routing scores)

SHOW_DENSE_BASELINE = (
    True  # also show a dense-FFN baseline block beside MoE for compute comparison
)


# ====================================================================
# Simple router model for visualization (not real compute)
# ====================================================================
@dataclass
class RouteDecision:
    # For each token, a list of up to top-k tuples: (expert_id, gate_score, used_by_capacity)
    assignments: List[List[Tuple[int, float, bool]]]
    # For experts: how many tokens assigned
    loads: List[int]
    # Which tokens overflowed and got dropped on second choice due to capacity (for red highlight)
    overflow_tokens: List[int]


def make_routes(
    n_tokens: int,
    n_experts: int,
    top_k: int,
    capacity_factor: float,
    rng: random.Random,
) -> RouteDecision:
    cap = int((n_tokens / float(n_experts)) * capacity_factor + 0.9999)  # ceil
    # random gate scores
    scores = [[rng.random() for _ in range(n_experts)] for _ in range(n_tokens)]
    # sort top-k per token
    topk = []
    for t in range(n_tokens):
        order = sorted(range(n_experts), key=lambda e: scores[t][e], reverse=True)
        picks = order[:top_k]
        row = [(e, scores[t][e]) for e in picks]
        topk.append(row)

    # first pass: assign first expert respecting capacity
    loads = [0] * n_experts
    assignments: List[List[Tuple[int, float, bool]]] = [[] for _ in range(n_tokens)]
    for t in range(n_tokens):
        e1, s1 = topk[t][0]
        use1 = loads[e1] < cap
        if use1:
            loads[e1] += 1
        assignments[t].append((e1, s1, use1))

    overflow_tokens = []
    # second pass: assign second expert if still unfilled or to show top-2; respect capacity
    if top_k >= 2:
        for t in range(n_tokens):
            e2, s2 = topk[t][1]
            # only add second if capacity remains
            use2 = loads[e2] < cap
            if use2:
                loads[e2] += 1
            else:
                overflow_tokens.append(t)
            assignments[t].append((e2, s2, use2))

    return RouteDecision(assignments, loads, overflow_tokens)


# ====================================================================
# Helpers to draw blocks and wiring
# ====================================================================
def token_row(scene: Scene, y: float, colors) -> VGroup:
    dots = VGroup()
    for i in range(N_TOKENS):
        d = Dot(color=colors[i], radius=0.12).move_to(
            LEFT * 5.5 + RIGHT * (i * 1.1) + UP * y
        )
        dots.add(d)
    scene.play(LaggedStart(*[Create(d) for d in dots], lag_ratio=0.05), run_time=0.8)
    return dots


def label_box(scene: Scene, box: Mobject, text: str, shift=(0, 0.7, 0), scale=0.5):
    t = (
        Text(text, weight=BOLD)
        .scale(scale)
        .next_to(box, UP)
        .shift(shift[0] * RIGHT + shift[1] * UP)
    )
    scene.play(FadeIn(t))
    return t


def block(
    scene: Scene,
    width: float,
    height: float,
    center: Tuple[float, float, float],
    color=BLUE_E,
) -> Rectangle:
    r = Rectangle(
        width=width, height=height, stroke_color=color, stroke_width=2
    ).move_to(center)
    scene.play(Create(r))
    return r


def dense_attention_block(scene: Scene, center) -> Rectangle:
    r = block(scene, width=4.8, height=1.4, center=center, color=BLUE_E)
    label_box(scene, r, "Self-Attention (dense)")
    return r


def dense_ffn_block(scene: Scene, center) -> Rectangle:
    r = block(scene, width=3.2, height=1.2, center=center, color=GREEN_E)
    label_box(scene, r, "Dense FFN")
    return r


def moe_block(
    scene: Scene, center, n_experts: int
) -> Tuple[Rectangle, List[Rectangle]]:
    # Container
    cont = block(scene, width=5.6, height=2.6, center=center, color=YELLOW_E)
    label_box(scene, cont, "MoE FFN (top-k routing)")
    # Experts inside
    experts = []
    cols = min(3, n_experts)
    rows = int((n_experts + cols - 1) // cols)  # FIXME: Unused
    start = np.array(center) + np.array([-2.2, 0.75, 0])  # top-left offset
    dx, dy = 2.2, 0.9
    for i in range(n_experts):
        r = Rectangle(
            width=1.6, height=0.6, stroke_color=YELLOW_D, stroke_width=2
        ).move_to(start + np.array([(i % cols) * dx, -(i // cols) * dy, 0]))
        experts.append(r)
    scene.play(LaggedStart(*[Create(e) for e in experts], lag_ratio=0.05), run_time=0.8)
    # Labels E0..E(n-1)
    labels = VGroup()
    for i, e in enumerate(experts):
        lbl = Text(f"E{i}", font_size=22).next_to(e, UP, buff=0.05)
        labels.add(lbl)
    scene.play(FadeIn(labels))
    return cont, experts


def arrow_path(
    scene: Scene, p1: np.ndarray, p2: np.ndarray, color=WHITE, width=2, rt=0.4
):
    arr = Arrow(p1, p2, buff=0.05, stroke_width=width, color=color)
    scene.play(Create(arr), run_time=rt)
    return arr


def compute_text(scene: Scene, pos, dense_cost: float, moe_cost: float):
    t1 = Text(f"Dense FFN compute ≈ {dense_cost:.0f}", font_size=28).move_to(
        np.array(pos) + np.array([0, 0.5, 0])
    )
    t2 = Text(f"MoE FFN compute ≈ {moe_cost:.0f}", font_size=28).move_to(
        np.array(pos) + np.array([0, 0.0, 0])
    )
    saving = max(0.0, 100.0 * (1.0 - moe_cost / max(dense_cost, 1e-9)))
    t3 = Text(
        f"Estimated savings ≈ {saving:.0f}%",
        font_size=28,
        color=GREEN if saving > 0 else RED,
    ).move_to(np.array(pos) + np.array([0, -0.5, 0]))
    scene.play(FadeIn(t1), FadeIn(t2), FadeIn(t3))
    return VGroup(t1, t2, t3)


# ====================================================================
# Main scene
# ====================================================================
class MoEVisualization(Scene):
    def construct(self):
        rng = random.Random(SEED)

        # Color each token (helps trace)
        palette = [
            BLUE_B,
            TEAL_B,
            GREEN_B,
            YELLOW_B,
            GOLD_B,
            ORANGE,
            RED_B,
            PURPLE_B,
            PINK,
            GRAY_BROWN,
        ]
        colors = [palette[i % len(palette)] for i in range(N_TOKENS)]

        # Row of tokens entering layer 0
        tok_row = token_row(self, y=3.0, colors=colors)

        # Per-layer visualization: Attention (dense) -> FFN (dense or MoE)
        current_positions = [d.get_center() for d in tok_row]
        for layer in range(N_LAYERS):
            # --- dense attention block (same for both dense & MoE stories) ---
            attn = dense_attention_block(self, center=(0, 1.8 - 1.8 * layer, 0))

            # Animate tokens flowing into attention and out (straight lines)
            # FIXME: Unused
            attn_in_arrows = [
                arrow_path(
                    self,
                    current_positions[i],
                    attn.get_top() + RIGHT * (-2.2 + 0.5 * i),
                    color=colors[i],
                    width=2,
                    rt=0.15,
                )
                for i in range(N_TOKENS)
            ]
            # "processing" effect
            self.wait(0.2)
            attn_out_slots = [
                attn.get_bottom() + RIGHT * (-2.2 + 0.5 * i) for i in range(N_TOKENS)
            ]

            # FIXME: Unused
            attn_out_arrows = [
                arrow_path(
                    self,
                    attn_out_slots[i],
                    np.array(attn_out_slots[i]) + np.array([0, -0.5, 0]),
                    color=colors[i],
                    width=2,
                    rt=0.15,
                )
                for i in range(N_TOKENS)
            ]
            current_positions = [
                np.array(attn_out_slots[i]) + np.array([0, -0.5, 0])
                for i in range(N_TOKENS)
            ]

            # --- two branches: Dense FFN (optional side-by-side) and MoE FFN ---
            branch_shift = 3.2
            dense_center = (-branch_shift, -0.2 - 1.8 * layer, 0)
            moe_center = (branch_shift, -0.2 - 1.8 * layer, 0)

            # Dense baseline (for comparison)
            if SHOW_DENSE_BASELINE:
                dense = dense_ffn_block(self, dense_center)
                dense_arrows = []
                for i in range(N_TOKENS):
                    p1 = current_positions[i] + np.array([-1.8, 0, 0])  # left branch
                    p2 = dense.get_top() + RIGHT * (-1.2 + 0.24 * i)
                    dense_arrows.append(
                        arrow_path(self, p1, p2, color=colors[i], width=2, rt=0.1)
                    )
                # out
                for i in range(N_TOKENS):
                    p2 = dense.get_bottom() + RIGHT * (-1.2 + 0.24 * i)
                    _ = arrow_path(
                        self, p2, p2 + DOWN * 0.5, color=colors[i], width=2, rt=0.1
                    )

            # MoE block
            moe_container, experts = moe_block(self, moe_center, N_EXPERTS)
            # Router label
            router_lbl = Text("Router (top-k)", font_size=26).next_to(
                moe_container, LEFT, buff=0.2
            )
            self.play(FadeIn(router_lbl))

            # Make routing decisions (toy logic)
            routes = make_routes(N_TOKENS, N_EXPERTS, TOP_K, CAPACITY_FACTOR, rng)

            # Draw input into router (just a fan-in arrow)
            for i in range(N_TOKENS):
                p1 = current_positions[i] + np.array([+1.8, 0, 0])  # right branch
                p2 = moe_container.get_left() + UP * (0.7 - 1.4 * (i / (N_TOKENS - 1)))
                arrow_path(self, p1, p2, color=colors[i], width=2, rt=0.1)

            # Dispatch to experts (animated)
            expert_centers = [e.get_center() for e in experts]
            cap = int((N_TOKENS / float(N_EXPERTS)) * CAPACITY_FACTOR + 0.9999)

            for t in range(N_TOKENS):
                assignments = routes.assignments[t]  # list of (expert, score, used)
                # up to top-k arrows per token
                for k_idx, (eid, score, used) in enumerate(assignments):
                    c = colors[t] if used else RED  # overflow -> red
                    src = (
                        moe_container.get_left()
                        + UP * (0.7 - 1.4 * (t / (N_TOKENS - 1)))
                        + RIGHT * 0.1
                    )
                    dst = expert_centers[eid] + LEFT * 0.6 + UP * (0.12 * (k_idx - 0.5))
                    arr = arrow_path(
                        self, src, dst, color=c, width=3 if used else 2, rt=0.12
                    )
                    # score tag
                    tag = Text(f"{score:.2f}", font_size=18, color=c).next_to(
                        arr, UP, buff=0.05
                    )
                    self.play(FadeIn(tag), run_time=0.05)

            # Combine back out of experts (fan-out)
            for t in range(N_TOKENS):
                # choose the "best" expert that actually used capacity (first True)
                chosen = None
                for eid, _, used in routes.assignments[t]:
                    if used:
                        chosen = eid
                        break
                if chosen is None:
                    # fully overflowed (rare with these settings) -> show red drop
                    drop = Dot(color=RED, radius=0.09).move_to(
                        moe_container.get_right() + DOWN * 0.2
                    )
                    self.play(FadeIn(drop), run_time=0.05)
                    continue
                src = expert_centers[chosen] + RIGHT * 0.6
                # go to the "output stream"
                out_y = moe_container.get_bottom()[1] - 0.6
                dst = (
                    np.array([moe_container.get_right()[0], out_y, 0])
                    + RIGHT * 0.0
                    + LEFT * 0.0
                )
                c = colors[t]
                arrow_path(self, src, dst, color=c, width=3, rt=0.12)

            # Show per-expert loads & capacity
            load_texts = VGroup()
            for eid, e in enumerate(experts):
                load = routes.loads[eid]
                lt = Text(f"{load}/{cap}", font_size=18).next_to(e, DOWN, buff=0.02)
                load_texts.add(lt)
            self.play(FadeIn(load_texts))

            # Simple compute proxy (for intuition, not actual FLOPs):
            # Dense FFN cost ~ N_TOKENS * d_ff   (constant factor dropped)
            # MoE FFN cost ~ (tokens actually processed) * d_ff
            dense_cost = float(N_TOKENS) * 1.0

            # FIXME: ambiguous variable name 'l'
            moe_tokens_processed = sum(min(cap, l) for l in routes.loads)
            # NOTE: this is intentionally simplified for teaching; real cost depends on top-k, batching, etc.
            moe_cost = float(moe_tokens_processed) / 1.0
            comp_box = compute_text(
                self,
                pos=(0, -2.2 - 1.8 * layer, 0),
                dense_cost=dense_cost,
                moe_cost=moe_cost,
            )

            self.wait(0.6)
            # Clear per-layer transient text if more layers ahead
            if layer < N_LAYERS - 1:
                self.play(FadeOut(comp_box), FadeOut(load_texts), FadeOut(router_lbl))

            # Prepare next layer input stream positions (just step down)
            current_positions = [
                np.array([0, -2.6 - 1.8 * layer, 0]) for _ in range(N_TOKENS)
            ]

        # Legend
        legend = (
            VGroup(
                Dot(color=WHITE, radius=0.10),
                Text(" token path", font_size=24),
                Dot(color=RED, radius=0.10),
                Text(" overflow / dropped (capacity)", font_size=24),
            )
            .arrange(RIGHT, buff=0.20)
            .to_edge(DOWN)
        )
        self.play(FadeIn(legend))
        self.wait(1.0)
