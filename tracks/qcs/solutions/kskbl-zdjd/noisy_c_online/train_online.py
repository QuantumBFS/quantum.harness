"""Train a random neural ensemble on a fresh-noise six-bit data stream."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from hidden_oracle import CleanDomainEvaluator, FreshNoiseStream, OUTPUT_BITS


class DenseLearner(nn.Module):
    """A formula-agnostic dense baseline with random initialization."""

    def __init__(self, hidden: int, depth: int) -> None:
        super().__init__()
        layers: list[nn.Module] = [nn.Linear(12, hidden), nn.GELU()]
        for _ in range(depth - 1):
            layers.extend((nn.Linear(hidden, hidden), nn.GELU()))
        layers.append(nn.Linear(hidden, OUTPUT_BITS))
        self.network = nn.Sequential(*layers)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)


class BitwiseDenseLearner(nn.Module):
    """Vectorized independent subnetworks prevent cross-bit interference."""

    def __init__(self, hidden: int, depth: int) -> None:
        super().__init__()
        self.input_weight = nn.Parameter(
            torch.empty(OUTPUT_BITS, 12, hidden)
        )
        self.input_bias = nn.Parameter(torch.zeros(OUTPUT_BITS, hidden))
        self.hidden_weights = nn.ParameterList(
            [
                nn.Parameter(torch.empty(OUTPUT_BITS, hidden, hidden))
                for _ in range(depth - 1)
            ]
        )
        self.hidden_biases = nn.ParameterList(
            [
                nn.Parameter(torch.zeros(OUTPUT_BITS, hidden))
                for _ in range(depth - 1)
            ]
        )
        self.output_weight = nn.Parameter(torch.empty(OUTPUT_BITS, hidden))
        self.output_bias = nn.Parameter(torch.zeros(OUTPUT_BITS))
        self.reset_parameters()

    def reset_parameters(self) -> None:
        for output in range(OUTPUT_BITS):
            nn.init.kaiming_uniform_(self.input_weight[output], a=math.sqrt(5))
            for weight in self.hidden_weights:
                nn.init.kaiming_uniform_(weight[output], a=math.sqrt(5))
            nn.init.kaiming_uniform_(
                self.output_weight[output : output + 1],
                a=math.sqrt(5),
            )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        hidden = torch.einsum("bi,oih->boh", inputs, self.input_weight)
        hidden = F.gelu(hidden + self.input_bias)
        for weight, bias in zip(
            self.hidden_weights,
            self.hidden_biases,
            strict=True,
        ):
            hidden = torch.einsum("boi,oih->boh", hidden, weight)
            hidden = F.gelu(hidden + bias)
        return torch.einsum("boh,oh->bo", hidden, self.output_weight) + self.output_bias


@dataclass
class Config:
    steps: int
    batch_size: int
    noise_rate: float
    ensemble_size: int
    hidden: int
    depth: int
    architecture: str
    learning_rate: float
    minimum_learning_rate: float
    learning_rate_schedule: str
    weight_decay: float
    eval_every: int
    base_seed: int
    device: str
    threads: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--noise-rate", type=float, default=0.25)
    parser.add_argument("--ensemble-size", type=int, default=4)
    parser.add_argument("--hidden", type=int, default=256)
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument(
        "--architecture",
        choices=("shared", "bitwise"),
        default="shared",
    )
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--minimum-learning-rate", type=float, default=2e-5)
    parser.add_argument(
        "--learning-rate-schedule",
        choices=("constant", "cosine"),
        default="constant",
    )
    parser.add_argument("--weight-decay", type=float, default=1e-6)
    parser.add_argument("--eval-every", type=int, default=20)
    parser.add_argument("--base-seed", type=int, default=7100)
    parser.add_argument("--threads", type=int, default=min(os.cpu_count() or 1, 12))
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def choose_device(requested: str) -> torch.device:
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but this PyTorch build has no CUDA")
        return torch.device("cuda")
    if requested == "auto" and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def make_model(architecture: str, hidden: int, depth: int) -> nn.Module:
    if architecture == "bitwise":
        return BitwiseDenseLearner(hidden, depth)
    return DenseLearner(hidden, depth)


def learning_rate_at_step(config: Config, step: int) -> float:
    if config.learning_rate_schedule == "constant":
        return config.learning_rate
    progress = min(max(step / config.steps, 0.0), 1.0)
    cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
    return config.minimum_learning_rate + (
        config.learning_rate - config.minimum_learning_rate
    ) * cosine


@torch.inference_mode()
def evaluate(
    models: list[nn.Module],
    evaluator: CleanDomainEvaluator,
) -> dict[str, object]:
    probabilities = torch.stack(
        [torch.sigmoid(model(evaluator.inputs)) for model in models],
        dim=0,
    )
    hard = probabilities >= 0.5
    ensemble_probability = probabilities.mean(dim=0)
    ensemble_hard = ensemble_probability >= 0.5
    targets = evaluator.targets.bool()

    bit_accuracy = (ensemble_hard == targets).float().mean().item()
    word_accuracy = (ensemble_hard == targets).all(dim=1).float().mean().item()
    clean_bce = F.binary_cross_entropy(
        ensemble_probability.clamp(1e-7, 1 - 1e-7),
        evaluator.targets,
    ).item()
    per_bit_accuracy = (
        (ensemble_hard == targets).float().mean(dim=0).cpu().tolist()
    )

    bit_weights = (2 ** torch.arange(OUTPUT_BITS, device=targets.device)).long()
    target_values = (targets.long() * bit_weights).sum(dim=1)
    predicted_values = (ensemble_hard.long() * bit_weights).sum(dim=1)
    normalized_mae = (
        (predicted_values - target_values).abs().float().mean().item() / 4095.0
    )

    q_hard = hard.float().mean(dim=0)
    bit_uncertainty = (
        4.0 * q_hard * (1.0 - q_hard)
    ).sum(dim=1).mean().item()
    member_values = (hard.long() * bit_weights).sum(dim=2).float()
    value_uncertainty = (
        member_values.var(dim=0, unbiased=False).mean().sqrt().item() / 4095.0
    )
    member_bit_accuracy = (
        (hard == targets.unsqueeze(0)).float().mean(dim=(1, 2)).cpu().tolist()
    )
    member_word_accuracy = (
        (hard == targets.unsqueeze(0))
        .all(dim=2)
        .float()
        .mean(dim=1)
        .cpu()
        .tolist()
    )

    return {
        "clean_bce": clean_bce,
        "bit_accuracy": bit_accuracy,
        "word_accuracy": word_accuracy,
        "normalized_mae": normalized_mae,
        "bit_uncertainty": bit_uncertainty,
        "value_uncertainty": value_uncertainty,
        "per_bit_accuracy": per_bit_accuracy,
        "member_bit_accuracy": member_bit_accuracy,
        "member_word_accuracy": member_word_accuracy,
    }


def main() -> None:
    args = parse_args()
    device = choose_device(args.device)
    torch.set_num_threads(args.threads)
    if device.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True

    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = Config(
        steps=args.steps,
        batch_size=args.batch_size,
        noise_rate=args.noise_rate,
        ensemble_size=args.ensemble_size,
        hidden=args.hidden,
        depth=args.depth,
        architecture=args.architecture,
        learning_rate=args.learning_rate,
        minimum_learning_rate=args.minimum_learning_rate,
        learning_rate_schedule=args.learning_rate_schedule,
        weight_decay=args.weight_decay,
        eval_every=args.eval_every,
        base_seed=args.base_seed,
        device=str(device),
        threads=args.threads,
    )
    (args.output_dir / "config.json").write_text(
        json.dumps(asdict(config), indent=2),
        encoding="utf-8",
    )

    models: list[nn.Module] = []
    optimizers: list[torch.optim.Optimizer] = []
    streams: list[FreshNoiseStream] = []
    for member in range(args.ensemble_size):
        seed = args.base_seed + 1009 * member
        set_seed(seed)
        model = make_model(args.architecture, args.hidden, args.depth).to(device)
        models.append(model)
        optimizers.append(
            torch.optim.AdamW(
                model.parameters(),
                lr=args.learning_rate,
                weight_decay=args.weight_decay,
            )
        )
        streams.append(
            FreshNoiseStream(
                batch_size=args.batch_size,
                noise_rate=args.noise_rate,
                seed=seed + 17,
                device=device,
            )
        )

    evaluator = CleanDomainEvaluator(device)
    ema_losses: list[float | None] = [None] * args.ensemble_size
    metrics: list[dict[str, object]] = []
    started = time.perf_counter()

    initial = evaluate(models, evaluator)
    metrics.append(
        {
            "step": 0,
            "examples_seen": 0,
            "elapsed_seconds": 0.0,
            "train_loss_ema": None,
            **initial,
        }
    )

    for step in range(1, args.steps + 1):
        current_learning_rate = learning_rate_at_step(config, step)
        for optimizer in optimizers:
            for group in optimizer.param_groups:
                group["lr"] = current_learning_rate
        for member, (model, optimizer, stream) in enumerate(
            zip(models, optimizers, streams, strict=True)
        ):
            model.train()
            inputs, noisy_targets = stream.sample()
            optimizer.zero_grad(set_to_none=True)
            clean_probability = torch.sigmoid(model(inputs))
            observed_probability = (
                args.noise_rate
                + (1.0 - 2.0 * args.noise_rate) * clean_probability
            )
            loss = F.binary_cross_entropy(
                observed_probability.clamp(1e-7, 1 - 1e-7),
                noisy_targets,
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            value = float(loss.detach())
            prior = ema_losses[member]
            ema_losses[member] = value if prior is None else 0.98 * prior + 0.02 * value

        if step % args.eval_every == 0 or step == args.steps:
            for model in models:
                model.eval()
            clean = evaluate(models, evaluator)
            record = {
                "step": step,
                "examples_seen": step * args.batch_size,
                "elapsed_seconds": time.perf_counter() - started,
                "learning_rate": current_learning_rate,
                "train_loss_ema": float(np.mean(ema_losses)),
                **clean,
            }
            metrics.append(record)
            print(
                f"step={step:6d} "
                f"train={record['train_loss_ema']:.5f} "
                f"clean_bce={record['clean_bce']:.5f} "
                f"bit={record['bit_accuracy']:.6f} "
                f"word={record['word_accuracy']:.6f} "
                f"Ubit={record['bit_uncertainty']:.4f} "
                f"Uvalue={record['value_uncertainty']:.6f} "
                f"wall={record['elapsed_seconds']:.1f}s",
                flush=True,
            )
            (args.output_dir / "metrics.json").write_text(
                json.dumps(metrics, indent=2),
                encoding="utf-8",
            )

    for member, model in enumerate(models):
        torch.save(
            {
                "model_state": model.state_dict(),
                "config": asdict(config),
                "member": member,
            },
            args.output_dir / f"model-{member:02d}.pt",
        )

    final = metrics[-1]
    run = {
        "kind": "online-noisy-hidden-function-recovery",
        "method": "randomly initialized dense neural ensemble",
        "config": asdict(config),
        "result": final,
        "verification": {
            "training_batches_use_fresh_inputs": True,
            "noise_mask_regenerated_every_batch": True,
            "clean_domain_used_for_gradients": False,
            "known_circuit_used_for_initialization": False,
            "clean_domain_size": 4096,
        },
    }
    (args.output_dir / "run.json").write_text(
        json.dumps(run, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
