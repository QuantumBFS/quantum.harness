#!/bin/sh
set -eu

export LC_ALL=C

search_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mode=${1:---check}

if [ "$mode" != "--check" ]; then
    echo "usage: $0 [--check]" >&2
    exit 2
fi

cargo test --locked --manifest-path "$search_root/Cargo.toml"
cargo check --locked --all-targets --manifest-path "$search_root/Cargo.toml"

echo "Standalone Occam source and hash-rooted release artifacts verified."
echo "The immutable v0.3 matrix and measured v2 matrix are reproduced by the parent repository gates."
