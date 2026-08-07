#!/usr/bin/env bash
#SBATCH --job-name=q66-render-papers
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=render-literature-%j.out
#SBATCH --error=render-literature-%j.err

set -euo pipefail

project_root=/work/home/hesicheng5/quantum-harness-ch66
command -v pdftotext
pdftotext "${project_root}/papers/gidney_stim_2021.pdf" "${project_root}/.knowledge/literature/gidney_stim_2021.txt"
pdftotext "${project_root}/papers/higgott_pymatching_2021.pdf" "${project_root}/.knowledge/literature/higgott_pymatching_2021.txt"
pdftotext "${project_root}/papers/higgott_sparse_blossom_2023.pdf" "${project_root}/.knowledge/literature/higgott_sparse_blossom_2023.txt"
wc -l "${project_root}/.knowledge/literature/"*.txt
