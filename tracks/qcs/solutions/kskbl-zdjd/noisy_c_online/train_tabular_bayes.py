"""Online Bayesian denoising baseline for the hidden six-bit Boolean map."""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from hidden_oracle import (
    CleanDomainEvaluator,
    DOMAIN_SIZE,
    FreshNoiseStream,
    OUTPUT_BITS,
)


@dataclass
class Config:
    steps: int
    batch_size: int
    noise_rate: float
    ensemble_size: int
    eval_every: int
    base_seed: int
    prior_jitter: float
    device: str


class BayesianTruthTable:
    """Accumulate the exact log-likelihood ratio supplied by noisy repeats."""

    def __init__(
        self,
        noise_rate: float,
        prior_jitter: float,
        seed: int,
        device: torch.device,
    ) -> None:
        generator = torch.Generator(device=device)
        generator.manual_seed(seed)
        self.log_odds = prior_jitter * torch.randn(
            DOMAIN_SIZE,
            OUTPUT_BITS,
            generator=generator,
            device=device,
        )
        self.observation_count = torch.zeros(
            DOMAIN_SIZE,
            dtype=torch.int64,
            device=device,
        )
        self.noise_rate = float(noise_rate)
        self.evidence_per_observation = math.log(
            (1.0 - noise_rate) / noise_rate
        )

    def probabilities(self) -> torch.Tensor:
        return torch.sigmoid(self.log_odds)

    def noisy_loss_before_update(
        self,
        ids: torch.Tensor,
        noisy_targets: torch.Tensor,
        noise_rate: float | None = None,
    ) -> torch.Tensor:
        if noise_rate is None:
            noise_rate = self.noise_rate
        clean_probability = torch.sigmoid(self.log_odds[ids])
        observed_probability = noise_rate + (
            1.0 - 2.0 * noise_rate
        ) * clean_probability
        return F.binary_cross_entropy(observed_probability, noisy_targets)

    def update(self, ids: torch.Tensor, noisy_targets: torch.Tensor) -> None:
        signed_evidence = (
            2.0 * noisy_targets - 1.0
        ) * self.evidence_per_observation
        self.log_odds.index_add_(0, ids, signed_evidence)
        self.observation_count.index_add_(
            0,
            ids,
            torch.ones_like(ids, dtype=torch.int64),
        )


class PairwiseNoiseBayesianTruthTable:
    """Infer an unknown global flip rate from repeated-label disagreements."""

    def __init__(
        self,
        initial_noise_rate: float,
        prior_jitter: float,
        noise_prior_pairs: float,
        seed: int,
        device: torch.device,
    ) -> None:
        if not 0.0 < initial_noise_rate < 0.5:
            raise ValueError("initial_noise_rate must lie between zero and 0.5")
        if noise_prior_pairs < 0.0:
            raise ValueError("noise_prior_pairs must be nonnegative")
        generator = torch.Generator(device=device)
        generator.manual_seed(seed)
        self.prior_log_odds = prior_jitter * torch.randn(
            DOMAIN_SIZE,
            OUTPUT_BITS,
            generator=generator,
            device=device,
            dtype=torch.float64,
        )
        self.log_odds = self.prior_log_odds.clone()
        self.ones_count = torch.zeros(
            DOMAIN_SIZE,
            OUTPUT_BITS,
            device=device,
            dtype=torch.float64,
        )
        self.observation_count = torch.zeros(
            DOMAIN_SIZE,
            dtype=torch.int64,
            device=device,
        )
        self.initial_noise_rate = float(initial_noise_rate)
        self.estimated_noise_rate = float(initial_noise_rate)
        self.estimated_noise_rates = torch.full(
            (OUTPUT_BITS,),
            initial_noise_rate,
            device=device,
            dtype=torch.float64,
        )
        self.calibrated_log_odds = self.prior_log_odds.clone()
        self.noise_prior_pairs = float(noise_prior_pairs)
        self.empirical_pair_disagreement: float | None = None
        self.effective_noise_pairs = 0.0

    def probabilities(self) -> torch.Tensor:
        return torch.sigmoid(self.log_odds).to(torch.float32)

    def calibrated_probabilities(self) -> torch.Tensor:
        return torch.sigmoid(self.calibrated_log_odds).to(torch.float32)

    def noisy_loss_before_update(
        self,
        ids: torch.Tensor,
        noisy_targets: torch.Tensor,
        noise_rate: float | None = None,
    ) -> torch.Tensor:
        del noise_rate
        clean_probability = torch.sigmoid(self.log_odds[ids]).to(
            noisy_targets.dtype
        )
        estimate = self.estimated_noise_rate
        observed_probability = estimate + (
            1.0 - 2.0 * estimate
        ) * clean_probability
        return F.binary_cross_entropy(observed_probability, noisy_targets)

    def _refresh_noise_and_posterior(self) -> None:
        counts = self.observation_count.to(torch.float64)[:, None]
        disagree_pairs_per_bit = torch.sum(
            self.ones_count * (counts - self.ones_count),
            dim=0,
        )
        disagree_pairs = disagree_pairs_per_bit.sum().item()
        total_pairs_per_bit = torch.sum(
            counts * (counts - 1.0)
        ).item() / 2.0
        total_pairs = total_pairs_per_bit * OUTPUT_BITS
        self.effective_noise_pairs = float(total_pairs)
        initial_disagreement = (
            2.0
            * self.initial_noise_rate
            * (1.0 - self.initial_noise_rate)
        )
        denominator = total_pairs + self.noise_prior_pairs
        if denominator > 0.0:
            pair_disagreement = (
                disagree_pairs
                + self.noise_prior_pairs * initial_disagreement
            ) / denominator
            self.empirical_pair_disagreement = float(
                disagree_pairs / total_pairs
            ) if total_pairs > 0.0 else None
            pair_disagreement = min(max(pair_disagreement, 0.0), 0.499999)
            estimate = 0.5 * (
                1.0 - math.sqrt(1.0 - 2.0 * pair_disagreement)
            )
            self.estimated_noise_rate = min(
                max(float(estimate), 1e-4),
                0.4999,
            )
        per_bit_denominator = (
            total_pairs_per_bit + self.noise_prior_pairs
        )
        if per_bit_denominator > 0.0:
            per_bit_disagreement = (
                disagree_pairs_per_bit
                + self.noise_prior_pairs * initial_disagreement
            ) / per_bit_denominator
            per_bit_disagreement = torch.clamp(
                per_bit_disagreement,
                min=0.0,
                max=0.499999,
            )
            self.estimated_noise_rates = torch.clamp(
                0.5
                * (
                    1.0
                    - torch.sqrt(1.0 - 2.0 * per_bit_disagreement)
                ),
                min=1e-4,
                max=0.4999,
            )
        evidence = math.log(
            (1.0 - self.estimated_noise_rate)
            / self.estimated_noise_rate
        )
        self.log_odds = self.prior_log_odds + (
            2.0 * self.ones_count - counts
        ) * evidence
        calibrated_evidence = torch.log(
            (1.0 - self.estimated_noise_rates)
            / self.estimated_noise_rates
        )
        self.calibrated_log_odds = self.prior_log_odds + (
            2.0 * self.ones_count - counts
        ) * calibrated_evidence[None, :]

    def update(self, ids: torch.Tensor, noisy_targets: torch.Tensor) -> None:
        self.ones_count.index_add_(
            0,
            ids,
            noisy_targets.to(torch.float64),
        )
        self.observation_count.index_add_(
            0,
            ids,
            torch.ones_like(ids, dtype=torch.int64),
        )
        self._refresh_noise_and_posterior()


class PairwisePerBitNoiseBayesianTruthTable:
    """Infer one flip rate per output bit from repeated-label disagreements."""

    def __init__(
        self,
        initial_noise_rate: float,
        prior_jitter: float,
        noise_prior_pairs: float,
        seed: int,
        device: torch.device,
    ) -> None:
        if not 0.0 < initial_noise_rate < 0.5:
            raise ValueError("initial_noise_rate must lie between zero and 0.5")
        if noise_prior_pairs < 0.0:
            raise ValueError("noise_prior_pairs must be nonnegative")
        generator = torch.Generator(device=device)
        generator.manual_seed(seed)
        self.prior_log_odds = prior_jitter * torch.randn(
            DOMAIN_SIZE,
            OUTPUT_BITS,
            generator=generator,
            device=device,
            dtype=torch.float64,
        )
        self.log_odds = self.prior_log_odds.clone()
        self.ones_count = torch.zeros(
            DOMAIN_SIZE,
            OUTPUT_BITS,
            device=device,
            dtype=torch.float64,
        )
        self.observation_count = torch.zeros(
            DOMAIN_SIZE,
            dtype=torch.int64,
            device=device,
        )
        self.initial_noise_rate = float(initial_noise_rate)
        self.estimated_noise_rates = torch.full(
            (OUTPUT_BITS,),
            initial_noise_rate,
            device=device,
            dtype=torch.float64,
        )
        self.estimated_noise_rate = float(initial_noise_rate)
        self.noise_prior_pairs = float(noise_prior_pairs)
        self.empirical_pair_disagreement = torch.full(
            (OUTPUT_BITS,),
            float("nan"),
            device=device,
            dtype=torch.float64,
        )
        self.effective_noise_pairs = 0.0

    def probabilities(self) -> torch.Tensor:
        return torch.sigmoid(self.log_odds).to(torch.float32)

    def calibrated_probabilities(self) -> torch.Tensor:
        return self.probabilities()

    def noisy_loss_before_update(
        self,
        ids: torch.Tensor,
        noisy_targets: torch.Tensor,
        noise_rate: float | None = None,
    ) -> torch.Tensor:
        del noise_rate
        clean_probability = torch.sigmoid(self.log_odds[ids]).to(
            noisy_targets.dtype
        )
        rates = self.estimated_noise_rates.to(noisy_targets.dtype)
        observed_probability = rates + (
            1.0 - 2.0 * rates
        ) * clean_probability
        return F.binary_cross_entropy(observed_probability, noisy_targets)

    def _refresh_noise_and_posterior(self) -> None:
        counts = self.observation_count.to(torch.float64)[:, None]
        disagree_pairs = torch.sum(
            self.ones_count * (counts - self.ones_count),
            dim=0,
        )
        total_pairs = torch.sum(
            counts * (counts - 1.0)
        ).item() / 2.0
        self.effective_noise_pairs = float(total_pairs * OUTPUT_BITS)
        initial_disagreement = (
            2.0
            * self.initial_noise_rate
            * (1.0 - self.initial_noise_rate)
        )
        denominator = total_pairs + self.noise_prior_pairs
        if denominator > 0.0:
            pair_disagreement = (
                disagree_pairs
                + self.noise_prior_pairs * initial_disagreement
            ) / denominator
            if total_pairs > 0.0:
                self.empirical_pair_disagreement = (
                    disagree_pairs / total_pairs
                )
            pair_disagreement = torch.clamp(
                pair_disagreement,
                min=0.0,
                max=0.499999,
            )
            estimates = 0.5 * (
                1.0 - torch.sqrt(1.0 - 2.0 * pair_disagreement)
            )
            self.estimated_noise_rates = torch.clamp(
                estimates,
                min=1e-4,
                max=0.4999,
            )
            self.estimated_noise_rate = float(
                self.estimated_noise_rates.mean().item()
            )
        evidence = torch.log(
            (1.0 - self.estimated_noise_rates)
            / self.estimated_noise_rates
        )
        self.log_odds = self.prior_log_odds + (
            2.0 * self.ones_count - counts
        ) * evidence[None, :]

    def update(self, ids: torch.Tensor, noisy_targets: torch.Tensor) -> None:
        self.ones_count.index_add_(
            0,
            ids,
            noisy_targets.to(torch.float64),
        )
        self.observation_count.index_add_(
            0,
            ids,
            torch.ones_like(ids, dtype=torch.int64),
        )
        self._refresh_noise_and_posterior()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=30_000)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--noise-rate", type=float, default=0.25)
    parser.add_argument("--ensemble-size", type=int, default=4)
    parser.add_argument("--eval-every", type=int, default=100)
    parser.add_argument("--base-seed", type=int, default=17_100)
    parser.add_argument("--prior-jitter", type=float, default=1e-6)
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


@torch.inference_mode()
def evaluate(
    learners: list[BayesianTruthTable],
    evaluator: CleanDomainEvaluator,
) -> dict[str, object]:
    probabilities = torch.stack(
        [learner.probabilities() for learner in learners]
    )
    member_bits = probabilities >= 0.5
    vote_fraction = member_bits.float().mean(dim=0)
    prediction = vote_fraction >= 0.5
    targets = evaluator.targets.bool()

    bit_accuracy = prediction.eq(targets).float().mean().item()
    word_accuracy = prediction.eq(targets).all(dim=1).float().mean().item()
    clean_bce = F.binary_cross_entropy(
        probabilities.mean(dim=0),
        evaluator.targets,
    ).item()

    bit_weights = (
        2 ** torch.arange(OUTPUT_BITS, device=evaluator.inputs.device)
    ).to(torch.int64)
    predicted_values = (prediction.to(torch.int64) * bit_weights).sum(dim=1)
    target_values = (targets.to(torch.int64) * bit_weights).sum(dim=1)
    normalized_mae = (
        (predicted_values - target_values).abs().float().mean() / 4095.0
    ).item()

    bit_uncertainty = (
        4.0 * vote_fraction * (1.0 - vote_fraction)
    ).sum(dim=1).mean().item()
    member_values = (
        member_bits.to(torch.int64) * bit_weights
    ).sum(dim=2).float()
    value_uncertainty = (
        member_values.var(dim=0, unbiased=False).mean().sqrt() / 4095.0
    ).item()

    return {
        "clean_bce": clean_bce,
        "bit_accuracy": bit_accuracy,
        "word_accuracy": word_accuracy,
        "normalized_mae": normalized_mae,
        "bit_uncertainty": bit_uncertainty,
        "value_uncertainty": value_uncertainty,
        "per_bit_accuracy": prediction.eq(targets).float().mean(dim=0).tolist(),
        "member_bit_accuracy": [
            bits.eq(targets).float().mean().item() for bits in member_bits
        ],
        "member_word_accuracy": [
            bits.eq(targets).all(dim=1).float().mean().item()
            for bits in member_bits
        ],
    }


def main() -> None:
    args = parse_args()
    if not 0.0 < args.noise_rate < 0.5:
        raise ValueError("noise-rate must lie strictly between zero and 0.5")
    if args.steps <= 0 or args.eval_every <= 0:
        raise ValueError("steps and eval-every must be positive")

    device = torch.device(args.device)
    set_seed(args.base_seed)
    config = Config(
        steps=args.steps,
        batch_size=args.batch_size,
        noise_rate=args.noise_rate,
        ensemble_size=args.ensemble_size,
        eval_every=args.eval_every,
        base_seed=args.base_seed,
        prior_jitter=args.prior_jitter,
        device=str(device),
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
    learners = [
        BayesianTruthTable(
            noise_rate=args.noise_rate,
            prior_jitter=args.prior_jitter,
            seed=args.base_seed + 10_000 + member,
            device=device,
        )
        for member in range(args.ensemble_size)
    ]
    evaluator = CleanDomainEvaluator(device)
    metrics: list[dict[str, object]] = []
    loss_ema: float | None = None
    input_weights = 2 ** torch.arange(12, device=device, dtype=torch.int64)
    start = time.perf_counter()

    for step in range(1, args.steps + 1):
        member_losses = []
        for stream, learner in zip(streams, learners, strict=True):
            inputs, noisy_targets = stream.sample()
            ids = (inputs.to(torch.int64) * input_weights).sum(dim=1)
            loss = learner.noisy_loss_before_update(
                ids,
                noisy_targets,
                args.noise_rate,
            )
            learner.update(ids, noisy_targets)
            member_losses.append(loss.item())
        mean_loss = float(np.mean(member_losses))
        loss_ema = (
            mean_loss
            if loss_ema is None
            else 0.98 * loss_ema + 0.02 * mean_loss
        )

        if step == 1 or step % args.eval_every == 0 or step == args.steps:
            record = {
                "step": step,
                "examples_seen": step * args.batch_size,
                "elapsed_seconds": time.perf_counter() - start,
                "train_loss_ema": loss_ema,
                **evaluate(learners, evaluator),
            }
            metrics.append(record)
            print(
                f"step={step:6d} "
                f"bit={record['bit_accuracy']:.6f} "
                f"word={record['word_accuracy']:.6f} "
                f"Ubit={record['bit_uncertainty']:.4f} "
                f"wall={record['elapsed_seconds']:.2f}s",
                flush=True,
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "config.json").write_text(
        json.dumps(asdict(config), indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )
    for member, learner in enumerate(learners):
        torch.save(
            {
                "log_odds": learner.log_odds,
                "observation_count": learner.observation_count,
            },
            args.output_dir / f"posterior-{member:02d}.pt",
        )
    final = metrics[-1]
    run = {
        "kind": "online-bayesian-denoising",
        "config": asdict(config),
        "verification": {
            "clean_domain_size": DOMAIN_SIZE,
            "clean_metrics_are_report_only": True,
            "clean_labels_used_for_updates": False,
            "target_formula_seeded": False,
            "existing_circuit_seeded": False,
            "fresh_noise_each_sample": True,
        },
        "final": final,
    }
    (args.output_dir / "run.json").write_text(
        json.dumps(run, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
