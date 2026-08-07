#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
alf_root="${project_root}/ALF"
pinned_commit="ff5600df97877ef1d080432d0068e157ff520ecd"
patch_files=(
    "${project_root}/patches/hirsch-binary.patch"
    "${project_root}/patches/free-uhf-boundary.patch"
    "${project_root}/patches/alf-path-archive.patch"
    "${project_root}/patches/green-location.patch"
    "${project_root}/patches/stable-center-weight.patch"
)
patched_sources=(
    "Prog/Hamiltonian_main_mod.F90"
    "Prog/Hamiltonians/Hamiltonian_Hubbard_Plain_Vanilla_smod.F90"
    "Prog/Makefile"
    "Prog/Path_archive_mod.F90"
    "Prog/main.F90"
    "Prog/control_mod.F90"
)
patched_sha256=(
    "256312f8728314cf2e658fa2f227e75f713796b810e68c6b9108754b201b781f"
    "feca980b79d5144ff69216815b2cf8a90bba94025c1c2b2b254b9209199e81ef"
    "1c209e3da207c3ff5dde0588ba9e299fd303da7aa1d31373f9e62acca95ef953"
    "4e1e1971d21b7af281331dfa83c7bdb38da4a86b40c77694768b55af2833fe78"
    "ce4b6fe4aba23045d49d0affbd1a91ee8fc93e84642df03b5c82ea607d3c29d8"
    "beb0f9996563b3239a5b6d2f580f3e7501f06e52a9b460392b711eaf80aa2187"
)

if [[ ! -d "${alf_root}/.git" ]]; then
    git clone --branch ALF-2.4 --single-branch \
        https://github.com/ALF-QMC/ALF.git "${alf_root}"
    git -C "${alf_root}" checkout --detach "${pinned_commit}"
fi

actual_commit="$(git -C "${alf_root}" rev-parse HEAD)"
if [[ "${actual_commit}" != "${pinned_commit}" ]]; then
    echo "ALF checkout is at ${actual_commit}, expected ${pinned_commit}" >&2
    exit 1
fi

if [[ "$(git -C "${alf_root}" branch --show-current)" != "codex/hirsch-binary" ]]; then
    if git -C "${alf_root}" show-ref --verify --quiet \
        refs/heads/codex/hirsch-binary; then
        git -C "${alf_root}" switch codex/hirsch-binary
    else
        git -C "${alf_root}" switch -c codex/hirsch-binary
    fi
fi

if [[ -z "$(git -C "${alf_root}" status --porcelain --untracked-files=all)" ]]; then
    for patch_file in "${patch_files[@]}"; do
        if ! git -C "${alf_root}" apply --check "${patch_file}"; then
            echo "ALF patch does not apply to the pinned clean checkout: ${patch_file}" >&2
            exit 1
        fi
        git -C "${alf_root}" apply "${patch_file}"
    done
else
    changed_files="$(
        git -C "${alf_root}" status --porcelain --untracked-files=all \
            | cut -c4- | sort
    )"
    expected_files="$(printf '%s\n' "${patched_sources[@]}" | sort)"
    hashes_ok=true
    for index in "${!patched_sources[@]}"; do
        actual="$(
            sha256sum "${alf_root}/${patched_sources[index]}" \
                | awk '{print $1}'
        )"
        if [[ "${actual}" != "${patched_sha256[index]}" ]]; then
            hashes_ok=false
        fi
    done
    if [[ "${changed_files}" != "${expected_files}" ]] \
        || [[ "${hashes_ok}" != true ]]; then
        echo "ALF checkout does not match the frozen patched source" >&2
        printf 'changed files: %s\n' "${changed_files}" >&2
        exit 1
    fi
fi

set +u
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
cd "${alf_root}"
source ./configure.sh Intel MPI STAB3 NO-INTERACTIVE >/dev/null
set -u
make all

mkdir -p "${project_root}/run/binary/bin"
cp -p Prog/ALF.out "${project_root}/run/binary/bin/ALF.binary.out"
cp -p Analysis/ana.out "${project_root}/run/binary/bin/ana.binary.out"
sha256sum \
    "${project_root}/run/binary/bin/ALF.binary.out" \
    "${project_root}/run/binary/bin/ana.binary.out"
