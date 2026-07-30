#!/usr/bin/env bash
set -eu

if [ "$#" -ne 1 ]; then
    echo "usage: $0 OUTPUT_DIR" >&2
    exit 2
fi

output_dir=$1
mkdir -p "$output_dir"

thermal=100
measurement=400
seed=20260729
lattices=${LATTICES:-"triangular honeycomb"}
sizes=${SIZES:-"4 8 12 16"}
summary="$output_dir/scaling.csv"
echo "lattice,L,N,beta,Gamma,Gamma_start,thermal,measurement,wall_seconds,user_seconds,max_rss_kb,exit_status,E,E_err,mx,mx_err,m2,m2_err,m4,m4_err,U,U_err" > "$summary"

for lattice in $lattices; do
    if [ "$lattice" = triangular ]; then
        gamma=4.76
        gamma_start=6.0
    else
        gamma=2.13
        gamma_start=3.0
    fi

    for L in $sizes; do
        beta=$((2 * L))
        if [ "$lattice" = triangular ]; then
            N=$((L * L))
        else
            N=$((2 * L * L))
        fi
        stem="$output_dir/${lattice}-L${L}"
        /usr/bin/time -f '%e,%U,%M,%x' -o "$stem.time.csv" \
            julia src/TIM_lattice_QMC.jl \
            "$lattice" "$L" "$L" -1.0 "$gamma" 0.0 "$beta" \
            "$thermal" "$measurement" "$seed" "$gamma_start" \
            > "$stem.out"
        IFS=, read -r wall user rss exit_status < "$stem.time.csv"
        result=$(cat "$stem.out")
        echo "$lattice,$L,$N,$beta,$gamma,$gamma_start,$thermal,$measurement,$wall,$user,$rss,$exit_status,$result" >> "$summary"
    done
done

echo "$summary"
