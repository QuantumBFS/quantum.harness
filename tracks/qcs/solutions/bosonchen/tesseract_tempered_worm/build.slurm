#!/usr/bin/env bash
#SBATCH --job-name=tw-build
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=/home/chentao/tesseract_20x_full_bosonchen/logs/tw-build-%j.out
#SBATCH --error=/home/chentao/tesseract_20x_full_bosonchen/logs/tw-build-%j.err

set -euo pipefail

source_root=/home/chentao/tesseract_20x_full_bosonchen/baseline-audit-work
bazel_binary=/home/chentao/tesseract_ler_2503_10988/bin/bazel-8.2.1-linux-x86_64
bazel_root=/home/chentao/tesseract_ler_2503_10988/bazel-root
bazel_output_base="$bazel_root/tempered-worm-output"
boost_repository=/home/chentao/tesseract_ler_2503_10988/bazel-root/67432b7e460eeacf0a75028a73838ac1/external/+_repo_rules+boost
cd "$source_root"
"$bazel_binary" --output_user_root="$bazel_root" --output_base="$bazel_output_base" test \
  --jobs="${SLURM_CPUS_PER_TASK:-8}" -c opt \
  --override_repository="+_repo_rules+boost=$boost_repository" \
  --test_output=errors \
  //tempered_worm:tempered_worm_test \
  //tempered_worm:phase0
sha256sum bazel-bin/tempered_worm/phase0
