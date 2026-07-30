"""Distill an online Bayesian denoiser into a compact randomly initialized model."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from hidden_oracle import (
    CleanDomainEvaluator,
    DOMAIN_SIZE,
    FreshNoiseStream,
    OUTPUT_BITS,
)
from train_online import evaluate, make_model, set_seed
from train_tabular_bayes import BayesianTruthTable


@dataclass
class Config:
    steps: int
    batch_size: int
    replay_batch_size: int
    replay_strategy: str
    candidate_multiplier: int
    active_exploration: float
    noise_rate: float
    ensemble_size: int
    architecture: str
    hidden: int
    depth: int
    learning_rate: float
    minimum_learning_rate: float
    learning_rate_schedule: str
    anneal_loss_threshold: float
    anneal_steps: int
    weight_decay: float
    confidence_power: float
    eval_every: int
    base_seed: int
    device: str
    threads: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=15_000)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--replay-batch-size", type=int, default=100)
    parser.add_argument(
        "--replay-strategy",
        choices=("uniform", "active"),
        default="active",
    )
    parser.add_argument("--candidate-multiplier", type=int, default=8)
    parser.add_argument("--active-exploration", type=float, default=0.20)
    parser.add_argument("--noise-rate", type=float, default=0.25)
    parser.add_argument("--ensemble-size", type=int, default=4)
    parser.add_argument(
        "--architecture",
        choices=("shared", "parity3"),
        default="parity3",
    )
    parser.add_argument("--hidden", type=int, default=160)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--minimum-learning-rate", type=float, default=5e-5)
    parser.add_argument(
        "--learning-rate-schedule",
        choices=("constant", "cosine", "loss-triggered"),
        default="cosine",
    )
    parser.add_argument("--anneal-loss-threshold", type=float, default=0.05)
    parser.add_argument("--anneal-steps", type=int, default=1000)
    parser.add_argument("--weight-decay", type=float, default=1e-6)
    parser.add_argument("--confidence-power", type=float, default=1.0)
    parser.add_argument("--eval-every", type=int, default=250)
    parser.add_argument("--base-seed", type=int, default=27_100)
    parser.add_argument("--threads", type=int, default=12)
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def learning_rate_at_step(
    config: Config,
    step: int,
    anneal_start_step: int | None,
) -> float:
    if config.learning_rate_schedule == "constant":
        return config.learning_rate
    if config.learning_rate_schedule == "loss-triggered":
        if anneal_start_step is None:
            return config.learning_rate
        progress = (step - anneal_start_step) / config.anneal_steps
    else:
        progress = step / config.steps
    progress = min(max(progress, 0.0), 1.0)
    cosine = 0.5 * (1.0 + np.cos(np.pi * progress))
    return config.minimum_learning_rate + (
        config.learning_rate - config.minimum_learning_rate
    ) * cosine


def ids_to_inputs(ids: torch.Tensor) -> torch.Tensor:
    shifts = torch.arange(12, device=ids.device)
    return ((ids[:, None] >> shifts[None, :]) & 1).to(torch.float32)


def posterior_distillation_loss(
    logits: torch.Tensor,
    posterior: torch.Tensor,
    confidence_power: float,
) -> torch.Tensor:
    confidence = (2.0 * posterior - 1.0).abs().pow(confidence_power)
    elementwise = F.binary_cross_entropy_with_logits(
        logits,
        posterior,
        reduction="none",
    )
    return (confidence * elementwise).sum() / confidence.sum().clamp_min(1.0)


@torch.no_grad()
def select_replay_batch(
    *,
    model: nn.Module,
    teacher: BayesianTruthTable,
    generator: torch.Generator,
    replay_batch_size: int,
    replay_strategy: str,
    candidate_multiplier: int,
    active_exploration: float,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor]:
    candidate_size = (
        replay_batch_size
        if replay_strategy == "uniform"
        else replay_batch_size * candidate_multiplier
    )
    candidate_ids = torch.randint(
        0,
        DOMAIN_SIZE,
        (candidate_size,),
        generator=generator,
        device=device,
    )
    candidate_posterior = torch.sigmoid(
        teacher.log_odds[candidate_ids]
    )
    if replay_strategy == "uniform":
        return candidate_ids, candidate_posterior

    candidate_inputs = ids_to_inputs(candidate_ids)
    model_probability = torch.sigmoid(model(candidate_inputs))
    confidence = (2.0 * candidate_posterior - 1.0).abs().mean(dim=1)
    disagreement = (
        model_probability - candidate_posterior
    ).abs().mean(dim=1)
    score = confidence * disagreement

    exploration_count = round(replay_batch_size * active_exploration)
    exploitation_count = replay_batch_size - exploration_count
    selected_parts: list[torch.Tensor] = []
    if exploitation_count:
        selected_parts.append(score.topk(exploitation_count).indices)
    if exploration_count:
        remaining = torch.randperm(
            candidate_size,
            generator=generator,
            device=device,
        )[:exploration_count]
        selected_parts.append(remaining)
    selected = torch.cat(selected_parts)
    return candidate_ids[selected], candidate_posterior[selected]


@torch.inference_mode()
def evaluate_teachers(
    teachers: list[BayesianTruthTable],
    evaluator: CleanDomainEvaluator,
) -> dict[str, float]:
    targets = evaluator.targets.bool()
    probabilities = torch.stack(
        [torch.sigmoid(teacher.log_odds) for teacher in teachers]
    )
    member_bits = probabilities >= 0.5
    ensemble_bits = probabilities.mean(dim=0) >= 0.5
    observation_count = torch.stack(
        [teacher.observation_count for teacher in teachers]
    )
    return {
        "teacher_bit_accuracy": ensemble_bits.eq(targets).float().mean().item(),
        "teacher_word_accuracy": (
            ensemble_bits.eq(targets).all(dim=1).float().mean().item()
        ),
        "teacher_member_coverage": (
            observation_count.gt(0).float().mean().item()
        ),
        "teacher_mean_observations": observation_count.float().mean().item(),
        "teacher_member_word_accuracy": (
            member_bits.eq(targets.unsqueeze(0))
            .all(dim=2)
            .float()
            .mean()
            .item()
        ),
    }


def main() -> None:
    args = parse_args()
    if not 0.0 < args.noise_rate < 0.5:
        raise ValueError("noise-rate must lie strictly between zero and 0.5")
    if args.steps <= 0 or args.eval_every <= 0:
        raise ValueError("steps and eval-every must be positive")
    if args.replay_batch_size <= 0 or args.candidate_multiplier <= 0:
        raise ValueError("replay sizes must be positive")
    if not 0.0 <= args.active_exploration <= 1.0:
        raise ValueError("active-exploration must lie between zero and one")
    if args.anneal_loss_threshold <= 0.0 or args.anneal_steps <= 0:
        raise ValueError("loss-triggered annealing settings must be positive")

    torch.set_num_threads(args.threads)
    device = torch.device(args.device)
    set_seed(args.base_seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = Config(
        steps=args.steps,
        batch_size=args.batch_size,
        replay_batch_size=args.replay_batch_size,
        replay_strategy=args.replay_strategy,
        candidate_multiplier=args.candidate_multiplier,
        active_exploration=args.active_exploration,
        noise_rate=args.noise_rate,
        ensemble_size=args.ensemble_size,
        architecture=args.architecture,
        hidden=args.hidden,
        depth=args.depth,
        learning_rate=args.learning_rate,
        minimum_learning_rate=args.minimum_learning_rate,
        learning_rate_schedule=args.learning_rate_schedule,
        anneal_loss_threshold=args.anneal_loss_threshold,
        anneal_steps=args.anneal_steps,
        weight_decay=args.weight_decay,
        confidence_power=args.confidence_power,
        eval_every=args.eval_every,
        base_seed=args.base_seed,
        device=str(device),
        threads=args.threads,
    )
    streams = [
        FreshNoiseStream(
            noise_rate=args.noise_rate,
            batch_size=args.batch_size,
            seed=args.base_seed + 101 * member,
            device=device,
        )
        for member in range(args.ensemble_size)
    ]
    teachers = [
        BayesianTruthTable(
            noise_rate=args.noise_rate,
            prior_jitter=1e-6,
            seed=args.base_seed + 10_000 + member,
            device=device,
        )
        for member in range(args.ensemble_size)
    ]
    replay_generators = [
        torch.Generator(device=device).manual_seed(
            args.base_seed + 20_000 + member
        )
        for member in range(args.ensemble_size)
    ]
    models: list[nn.Module] = []
    optimizers: list[torch.optim.Optimizer] = []
    for member in range(args.ensemble_size):
        set_seed(args.base_seed + 30_000 + member)
        model = make_model(args.architecture, args.hidden, args.depth).to(device)
        models.append(model)
        optimizers.append(
            torch.optim.AdamW(
                model.parameters(),
                lr=args.learning_rate,
                weight_decay=args.weight_decay,
            )
        )

    evaluator = CleanDomainEvaluator(device)
    metrics: list[dict[str, object]] = []
    loss_ema: float | None = None
    anneal_start_step: int | None = None
    input_weights = 2 ** torch.arange(12, device=device, dtype=torch.int64)
    start = time.perf_counter()
    (args.output_dir / "config.json").write_text(
        json.dumps(asdict(config), indent=2),
        encoding="utf-8",
    )

    for step in range(1, args.steps + 1):
        learning_rate = learning_rate_at_step(
            config,
            step,
            anneal_start_step,
        )
        member_losses = []
        for stream, teacher, generator, model, optimizer in zip(
            streams,
            teachers,
            replay_generators,
            models,
            optimizers,
            strict=True,
        ):
            fresh_inputs, noisy_targets = stream.sample()
            fresh_ids = (
                fresh_inputs.to(torch.int64) * input_weights
            ).sum(dim=1)
            teacher.update(fresh_ids, noisy_targets)

            replay_ids, posterior = select_replay_batch(
                model=model,
                teacher=teacher,
                generator=generator,
                replay_batch_size=args.replay_batch_size,
                replay_strategy=args.replay_strategy,
                candidate_multiplier=args.candidate_multiplier,
                active_exploration=args.active_exploration,
                device=device,
            )
            replay_inputs = ids_to_inputs(replay_ids)
            for group in optimizer.param_groups:
                group["lr"] = learning_rate
            optimizer.zero_grad(set_to_none=True)
            logits = model(replay_inputs)
            loss = posterior_distillation_loss(
                logits,
                posterior,
                args.confidence_power,
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            member_losses.append(loss.item())

        mean_loss = float(np.mean(member_losses))
        loss_ema = (
            mean_loss
            if loss_ema is None
            else 0.98 * loss_ema + 0.02 * mean_loss
        )
        if (
            config.learning_rate_schedule == "loss-triggered"
            and anneal_start_step is None
            and loss_ema <= config.anneal_loss_threshold
        ):
            anneal_start_step = step + 1
        if step == 1 or step % args.eval_every == 0 or step == args.steps:
            record = {
                "step": step,
                "examples_seen": step * args.batch_size,
                "elapsed_seconds": time.perf_counter() - start,
                "learning_rate": learning_rate,
                "anneal_start_step": anneal_start_step,
                "train_loss_ema": loss_ema,
                **evaluate(models, evaluator),
                **evaluate_teachers(teachers, evaluator),
            }
            metrics.append(record)
            print(
                f"step={step:6d} "
                f"distill={loss_ema:.5f} "
                f"clean_bce={record['clean_bce']:.5f} "
                f"bit={record['bit_accuracy']:.6f} "
                f"word={record['word_accuracy']:.6f} "
                f"teacher={record['teacher_word_accuracy']:.6f} "
                f"Ubit={record['bit_uncertainty']:.4f} "
                f"wall={record['elapsed_seconds']:.1f}s",
                flush=True,
            )
            (args.output_dir / "metrics.json").write_text(
                json.dumps(metrics, indent=2),
                encoding="utf-8",
            )

    for member, (model, teacher) in enumerate(
        zip(models, teachers, strict=True)
    ):
        torch.save(model.state_dict(), args.output_dir / f"model-{member:02d}.pt")
        torch.save(
            {
                "log_odds": teacher.log_odds,
                "observation_count": teacher.observation_count,
            },
            args.output_dir / f"teacher-{member:02d}.pt",
        )
    final = metrics[-1]
    run = {
        "kind": "online-posterior-replay-distillation",
        "config": asdict(config),
        "verification": {
            "clean_domain_size": DOMAIN_SIZE,
            "clean_metrics_are_report_only": True,
            "clean_labels_used_for_updates": False,
            "teacher_uses_only_fresh_noisy_stream": True,
            "target_formula_seeded": False,
            "existing_circuit_seeded": False,
            "fresh_noise_each_sample": True,
        },
        "anneal_start_step": anneal_start_step,
        "final": final,
    }
    (args.output_dir / "run.json").write_text(
        json.dumps(run, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
