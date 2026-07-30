#!/usr/bin/env julia

"""
Build portable SVG validation figures for the finite OBC TFIM benchmark.

The script uses only Julia standard libraries. It deliberately compares only
beta values present in every displayed data set; it never interpolates.

From the HarnessingQuantum-2026 repository root:

    julia plots/qmc-validation/build_energy_comparison_figures.jl

The repository currently has no frozen 2x2 tanTRG result. With no additional
argument the script therefore emits an explicitly named ED+SSE-only 2x2
figure. Once a real tanTRG CSV exists, use:

    julia plots/qmc-validation/build_energy_comparison_figures.jl \
      --l2-tantrg=/path/to/tfim-l2-tantrg-energy.csv \
      --require-l2-tantrg

The tanTRG CSV schema is:

    beta,tantrg_energy_per_site
"""

using Printf
using SHA

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const DEFAULT_OUTPUT_DIRECTORY = @__DIR__
const L2_ED_SSE_PATH = joinpath(
    REPOSITORY_ROOT,
    "notes",
    "assets",
    "tfim-algorithm-differences-2026-07-28",
    "l2-ed-qmc-peps-comparison.csv",
)
const L4_QMC_PATH = joinpath(
    REPOSITORY_ROOT,
    "QuantumMC-Methods",
    "results",
    "validation",
    "tables",
    "tfim-sse-l4-full-peps-metts-aggregate-2026-07-29.csv",
)
const L4_QMC_HIGH_T_PATH = joinpath(
    REPOSITORY_ROOT,
    "QuantumMC-Methods",
    "results",
    "validation",
    "tables",
    "tfim-sse-l4-high-temperature-extension-2026-07-29.csv",
)
const L4_TANTRG_PATH = joinpath(
    REPOSITORY_ROOT,
    "notes",
    "assets",
    "tfim-algorithm-differences-2026-07-28",
    "l4-tantrg-34points.csv",
)
const DEFAULT_L2_TANTRG_PATH =
    joinpath(@__DIR__, "data", "tfim-l2-tantrg-energy.csv")

const EXPECTED_L2_ED_SSE_SHA256 =
    "544c74f9495037afd8353b8519562a1bc452e1853e0dc01b081b1a92e8ae6af4"
const EXPECTED_L4_QMC_SHA256 =
    "f4a9391f9d4a6e5ca672d093d72aa481ab7285cfbcb149617623d1ad827ac142"
const EXPECTED_L4_QMC_HIGH_T_SHA256 =
    "df125651ec8c2c3899503ef1041b330963cd52b64cbe630fa62145d376db4089"
const EXPECTED_L4_TANTRG_SHA256 =
    "4defcdcc362d49025fedf17952162d94f6b9e77de58821de805d0502dd53e992"

const WIDTH = 1280.0
const HEIGHT = 940.0
const LEFT = 132.0
const RIGHT = 50.0
const PLOT_WIDTH = WIDTH - LEFT - RIGHT
const TOP_Y = 182.0
const TOP_HEIGHT = 330.0
const BOTTOM_Y = 615.0
const BOTTOM_HEIGHT = 230.0

const COLOR_ED = "#222222"
const COLOR_QMC = "#0072B2"
const COLOR_TANTRG = "#D55E00"
const COLOR_GRID = "#D8DDE3"
const COLOR_TEXT = "#20252A"
const COLOR_MUTED = "#5B6570"
const COLOR_QMC_BAND = "#B9DDF2"

struct Series
    beta::Vector{Float64}
    energy::Vector{Float64}
    error::Vector{Float64}
end

file_sha256(path) = bytes2hex(sha256(read(path)))

function verify_source(path, expected_hash)
    isfile(path) || error("missing frozen input: $path")
    actual_hash = file_sha256(path)
    actual_hash == expected_hash ||
        error("input hash mismatch for $path\nexpected $expected_hash\nactual   $actual_hash")
    return actual_hash
end

function parse_arguments(arguments)
    output_directory = DEFAULT_OUTPUT_DIRECTORY
    l2_sse_path = L2_ED_SSE_PATH
    l2_tantrg_path = DEFAULT_L2_TANTRG_PATH
    require_l2_tantrg = false
    for argument in arguments
        if startswith(argument, "--output-dir=")
            output_directory = abspath(split(argument, '='; limit=2)[2])
        elseif startswith(argument, "--l2-sse=")
            l2_sse_path = abspath(split(argument, '='; limit=2)[2])
        elseif startswith(argument, "--l2-tantrg=")
            l2_tantrg_path = abspath(split(argument, '='; limit=2)[2])
        elseif argument == "--require-l2-tantrg"
            require_l2_tantrg = true
        else
            error("unknown argument: $argument")
        end
    end
    return (;
        output_directory,
        l2_sse_path,
        l2_tantrg_path,
        require_l2_tantrg,
    )
end

function read_csv(path)
    lines = readlines(path)
    isempty(lines) && error("empty CSV: $path")
    header = split(first(lines), ',')
    positions = Dict(name => index for (index, name) in pairs(header))
    rows = [split(line, ',') for line in lines[2:end] if !isempty(strip(line))]
    return positions, rows
end

number(row, positions, name) = parse(Float64, row[positions[name]])

function require_columns(positions, names, path)
    missing = [name for name in names if !haskey(positions, name)]
    isempty(missing) ||
        error("missing columns in $path: $(join(missing, ", "))")
end

function load_l2_ed_sse(path)
    positions, rows = read_csv(path)
    ed_column = haskey(positions, "ed_energy_per_site") ?
        "ed_energy_per_site" : "exact_energy_per_site"
    qmc_error_column = haskey(positions, "qmc_se_per_site") ?
        "qmc_se_per_site" : "qmc_final_mcse"
    require_columns(
        positions,
        [
            "beta",
            ed_column,
            "qmc_energy_per_site",
            qmc_error_column,
        ],
        path,
    )
    beta = number.(rows, Ref(positions), "beta")
    issorted(beta) || error("2x2 beta grid is not sorted")
    ed = Series(
        beta,
        number.(rows, Ref(positions), ed_column),
        zeros(length(rows)),
    )
    qmc = Series(
        beta,
        number.(rows, Ref(positions), "qmc_energy_per_site"),
        number.(rows, Ref(positions), qmc_error_column),
    )
    return ed, qmc
end

const SUPERSCRIPT_DIGITS = Dict(
    '-' => '⁻',
    '0' => '⁰',
    '1' => '¹',
    '2' => '²',
    '3' => '³',
    '4' => '⁴',
    '5' => '⁵',
    '6' => '⁶',
    '7' => '⁷',
    '8' => '⁸',
    '9' => '⁹',
)

superscript_integer(value) =
    join(SUPERSCRIPT_DIGITS[digit] for digit in string(value))

function power_of_two_label(value)
    value > 0 || return string(value)
    exponent = round(Int, log2(value))
    return 2^exponent == value ?
        "2$(superscript_integer(exponent))" : string(value)
end

function format_log_tick(value)
    value > 0 || error("logarithmic tick must be positive")
    exponent = round(Int, log10(value))
    return isapprox(value, 10.0^exponent; rtol=1e-10) ?
        "10$(superscript_integer(exponent))" : @sprintf("%.1e", value)
end

function l2_qmc_sampling_label(path)
    positions, rows = read_csv(path)
    if haskey(positions, "replicas") &&
       haskey(positions, "measurement_sweeps_per_replica")
        replicas = unique(
            parse.(Int, getindex.(rows, positions["replicas"])),
        )
        sweeps = unique(
            parse.(
                Int,
                getindex.(rows, positions["measurement_sweeps_per_replica"]),
            ),
        )
        length(replicas) == 1 ||
            error("2x2 QMC input has nonuniform replica counts")
        length(sweeps) == 1 ||
            error("2x2 QMC input has nonuniform measurement schedules")
        return "SSE-QMC — $(only(replicas)) replicas/β × " *
               "$(power_of_two_label(only(sweeps))) sweeps; ±1 MCSE"
    end
    return "SSE-QMC — 20 replicas/β; 2²¹ sweeps at β=1,2; " *
           "2¹⁸ otherwise; ±1 MCSE"
end

function load_l2_tantrg(path, expected_beta)
    positions, rows = read_csv(path)
    require_columns(positions, ["beta", "tantrg_energy_per_site"], path)
    by_beta = Dict(
        number(row, positions, "beta") =>
            number(row, positions, "tantrg_energy_per_site")
        for row in rows
    )
    missing = [beta for beta in expected_beta if !haskey(by_beta, beta)]
    isempty(missing) ||
        error("2x2 tanTRG data miss exact beta points: $(join(missing, ", "))")
    return Series(
        copy(expected_beta),
        [by_beta[beta] for beta in expected_beta],
        zeros(length(expected_beta)),
    )
end

function append_qmc_rows!(by_beta, path)
    positions, rows = read_csv(path)
    require_columns(
        positions,
        [
            "Lx",
            "Ly",
            "boundary",
            "J",
            "h",
            "beta",
            "qmc_energy_per_site",
            "qmc_final_mcse",
        ],
        path,
    )
    for row in rows
        number(row, positions, "Lx") == 4 || error("unexpected Lx in $path")
        number(row, positions, "Ly") == 4 || error("unexpected Ly in $path")
        row[positions["boundary"]] == "OBC" ||
            error("unexpected boundary in $path")
        number(row, positions, "J") == 1.0 || error("unexpected J in $path")
        number(row, positions, "h") == 0.5 || error("unexpected h in $path")
        beta = number(row, positions, "beta")
        haskey(by_beta, beta) && error("duplicate QMC beta=$beta")
        by_beta[beta] = (
            number(row, positions, "qmc_energy_per_site"),
            number(row, positions, "qmc_final_mcse"),
        )
    end
    return by_beta
end

function load_l4_sse_tantrg(qmc_path, qmc_high_t_path, tantrg_path)
    qmc_by_beta = Dict{Float64,Tuple{Float64,Float64}}()
    append_qmc_rows!(qmc_by_beta, qmc_path)
    append_qmc_rows!(qmc_by_beta, qmc_high_t_path)

    positions, rows = read_csv(tantrg_path)
    require_columns(
        positions,
        ["beta", "tantrg_energy_per_site"],
        tantrg_path,
    )
    tantrg_by_beta = Dict(
        number(row, positions, "beta") =>
            number(row, positions, "tantrg_energy_per_site")
        for row in rows
    )
    beta = sort(collect(intersect(keys(qmc_by_beta), keys(tantrg_by_beta))))
    length(beta) == 25 ||
        error("expected 25 exact 4x4 common beta points, found $(length(beta))")
    qmc = Series(
        beta,
        [qmc_by_beta[value][1] for value in beta],
        [qmc_by_beta[value][2] for value in beta],
    )
    tantrg = Series(
        beta,
        [tantrg_by_beta[value] for value in beta],
        zeros(length(beta)),
    )
    return qmc, tantrg
end

xml_escape(text) = replace(
    string(text),
    '&' => "&amp;",
    '<' => "&lt;",
    '>' => "&gt;",
    '"' => "&quot;",
)

function atomic_write(writer, path)
    mkpath(dirname(path))
    temporary = "$path.tmp.$(getpid())"
    open(temporary, "w") do io
        writer(io)
        flush(io)
    end
    mv(temporary, path; force=true)
    return path
end

function text_svg(io, x, y, text;
                  size=18, anchor="middle", color=COLOR_TEXT,
                  weight="400", rotate=nothing)
    transform = isnothing(rotate) ? "" :
        " transform=\"rotate($(rotate) $(x) $(y))\""
    println(
        io,
        "<text x=\"$(x)\" y=\"$(y)\" text-anchor=\"$(anchor)\" " *
        "font-family=\"DejaVu Sans,Arial,sans-serif\" font-size=\"$(size)\" " *
        "font-weight=\"$(weight)\" fill=\"$(color)\"$(transform)>" *
        "$(xml_escape(text))</text>",
    )
end

function line_svg(io, x1, y1, x2, y2;
                  color=COLOR_TEXT, width=1.5, dash=nothing, opacity=1.0)
    dash_attribute = isnothing(dash) ? "" : " stroke-dasharray=\"$(dash)\""
    println(
        io,
        "<line x1=\"$(x1)\" y1=\"$(y1)\" x2=\"$(x2)\" y2=\"$(y2)\" " *
        "stroke=\"$(color)\" stroke-width=\"$(width)\" opacity=\"$(opacity)\"" *
        "$(dash_attribute)/>",
    )
end

function polyline_svg(io, xs, ys; color, width=2.6, dash=nothing)
    points = join(("$(x),$(y)" for (x, y) in zip(xs, ys)), ' ')
    dash_attribute = isnothing(dash) ? "" : " stroke-dasharray=\"$(dash)\""
    println(
        io,
        "<polyline points=\"$(points)\" fill=\"none\" stroke=\"$(color)\" " *
        "stroke-width=\"$(width)\" stroke-linecap=\"round\" " *
        "stroke-linejoin=\"round\"$(dash_attribute)/>",
    )
end

function circle_svg(io, x, y; radius=5.0, fill=COLOR_QMC,
                    stroke=fill, width=1.5)
    println(
        io,
        "<circle cx=\"$(x)\" cy=\"$(y)\" r=\"$(radius)\" fill=\"$(fill)\" " *
        "stroke=\"$(stroke)\" stroke-width=\"$(width)\"/>",
    )
end

function diamond_svg(io, x, y; radius=6.0, fill=COLOR_QMC)
    points = join(
        (
            "$(x),$(y-radius)",
            "$(x+radius),$(y)",
            "$(x),$(y+radius)",
            "$(x-radius),$(y)",
        ),
        ' ',
    )
    println(
        io,
        "<polygon points=\"$(points)\" fill=\"$(fill)\" stroke=\"$(fill)\"/>",
    )
end

function scales(beta, values, errors;
                relative=false, logx=false, logy=false)
    xmin, xmax = extrema(beta)
    if logy
        positive_values = filter(>(0.0), values)
        isempty(positive_values) &&
            error("logarithmic y axis requires at least one positive value")
        length(positive_values) == length(values) ||
            error("logarithmic y axis received a nonpositive value")
        raw_min, raw_max = extrema(positive_values)
        ymin = 10.0^floor(log10(raw_min))
        ymax = 10.0^ceil(log10(raw_max))
        ymin == ymax && (ymin /= 10; ymax *= 10)
    else
        raw_min = minimum(values .- errors)
        raw_max = maximum(values .+ errors)
        if relative
            magnitude = max(abs(raw_min), abs(raw_max), 1e-8)
            ymin, ymax = -1.18magnitude, 1.18magnitude
        else
            span = max(raw_max - raw_min, 1e-8)
            ymin, ymax = raw_min - 0.10span, raw_max + 0.10span
        end
    end
    xmap = if logx
        log_min, log_max = log10(xmin), log10(xmax)
        x -> LEFT + (log10(x) - log_min) / (log_max - log_min) * PLOT_WIDTH
    else
        x -> LEFT + (x - xmin) / (xmax - xmin) * PLOT_WIDTH
    end
    return (; xmin, xmax, ymin, ymax, xmap, logx, logy)
end

ymap(value, ymin, ymax, top, height) =
    top + height - (value - ymin) / (ymax - ymin) * height

function mapped_y(value, scale, top, height)
    if scale.logy
        value > 0 || error("cannot place nonpositive value on logarithmic y axis")
        return top + height -
               (log10(value) - log10(scale.ymin)) /
               (log10(scale.ymax) - log10(scale.ymin)) * height
    end
    return ymap(value, scale.ymin, scale.ymax, top, height)
end

function tick_values(minimum_value, maximum_value, count)
    return collect(range(minimum_value, maximum_value; length=count))
end

function format_beta(value)
    value < 0.1 && return @sprintf("%.3g", value)
    rounded = round(value)
    return isapprox(value, rounded; atol=1e-10) ?
        @sprintf("%.0f", rounded) : @sprintf("%.1f", value)
end

format_energy(value) = @sprintf("%.3f", value)
format_relative(value) = abs(value) >= 0.1 ?
    @sprintf("%.2f", value) : @sprintf("%.3f", value)

function draw_axes(io, scale, top, height;
                   ylabel, xlabel=nothing, relative=false,
                   x_tick_count=6, y_tick_count=5,
                   custom_x_ticks=nothing)
    y_ticks = if scale.logy
        exponents = collect(
            ceil(Int, log10(scale.ymin)):floor(Int, log10(scale.ymax)),
        )
        if length(exponents) > 7
            stride = ceil(Int, (length(exponents) - 1) / 6)
            displayed = exponents[1:stride:end]
            last(displayed) == last(exponents) || push!(displayed, last(exponents))
            exponents = displayed
        end
        10.0 .^ exponents
    else
        tick_values(scale.ymin, scale.ymax, y_tick_count)
    end
    for value in y_ticks
        y = mapped_y(value, scale, top, height)
        line_svg(io, LEFT, y, LEFT + PLOT_WIDTH, y;
                 color=COLOR_GRID, width=1.0)
        text_svg(
            io,
            LEFT - 12,
            y + 6,
            scale.logy ? format_log_tick(value) :
            relative ? format_relative(value) : format_energy(value);
            size=18,
            anchor="end",
            color=COLOR_MUTED,
        )
    end
    x_ticks = if !isnothing(custom_x_ticks)
        custom_x_ticks
    elseif scale.logx
        candidates = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
        [value for value in candidates
         if scale.xmin <= value <= scale.xmax]
    else
        tick_values(scale.xmin, scale.xmax, x_tick_count)
    end
    for value in x_ticks
        x = scale.xmap(value)
        line_svg(io, x, top, x, top + height;
                 color=COLOR_GRID, width=1.0)
        text_svg(
            io,
            x,
            top + height + 25,
            format_beta(value);
            size=18,
            color=COLOR_MUTED,
        )
    end
    line_svg(io, LEFT, top, LEFT, top + height;
             color=COLOR_TEXT, width=1.7)
    line_svg(io, LEFT, top + height, LEFT + PLOT_WIDTH, top + height;
             color=COLOR_TEXT, width=1.7)
    text_svg(
        io,
        31,
        top + height / 2,
        ylabel;
        size=24,
        rotate=-90,
    )
    if !isnothing(xlabel)
        text_svg(io, LEFT + PLOT_WIDTH / 2, top + height + 68, xlabel; size=24)
    end
end

function draw_errorbars(io, series, scale, top, height;
                        color=COLOR_QMC, width=1.6)
    for (beta, value, error) in zip(series.beta, series.energy, series.error)
        x = scale.xmap(beta)
        y_low = mapped_y(value - error, scale, top, height)
        y_high = mapped_y(value + error, scale, top, height)
        line_svg(io, x, y_low, x, y_high; color, width)
        line_svg(io, x - 4.5, y_low, x + 4.5, y_low; color, width)
        line_svg(io, x - 4.5, y_high, x + 4.5, y_high; color, width)
    end
end

function draw_series(io, series, scale, top, height;
                     color, line=true, marker=:circle, open=false,
                     width=2.6, marker_radius=5.0, dash=nothing)
    xs = scale.xmap.(series.beta)
    ys = [mapped_y(value, scale, top, height) for value in series.energy]
    line && polyline_svg(io, xs, ys; color, width, dash)
    for (x, y) in zip(xs, ys)
        if marker == :none
            continue
        elseif marker == :diamond
            diamond_svg(io, x, y; radius=marker_radius, fill=color)
        else
            circle_svg(
                io,
                x,
                y;
                radius=marker_radius,
                fill=open ? "none" : color,
                stroke=color,
                width=2.0,
            )
        end
    end
end

function draw_qmc_band(io, beta, relative_error, scale, top, height)
    upper = [
        "$(scale.xmap(b)),$(ymap(e, scale.ymin, scale.ymax, top, height))"
        for (b, e) in zip(beta, relative_error)
    ]
    lower = [
        "$(scale.xmap(b)),$(ymap(-e, scale.ymin, scale.ymax, top, height))"
        for (b, e) in reverse(collect(zip(beta, relative_error)))
    ]
    points = join(vcat(upper, lower), ' ')
    println(
        io,
        "<polygon points=\"$(points)\" fill=\"$(COLOR_QMC_BAND)\" " *
        "fill-opacity=\"0.58\" stroke=\"none\"/>",
    )
end

function draw_legend(io, entries; x_start=LEFT + 18)
    x = x_start
    y = TOP_Y + 26
    for entry in entries
        color, label, style = entry
        if style == :line
            line_svg(io, x, y - 5, x + 30, y - 5; color, width=2.8)
        elseif style == :dashed
            line_svg(
                io,
                x,
                y - 5,
                x + 30,
                y - 5;
                color,
                width=2.2,
                dash="7 5",
            )
        elseif style == :open
            line_svg(io, x, y - 5, x + 30, y - 5; color, width=2.4)
            circle_svg(io, x + 15, y - 5; radius=4.5, fill="none",
                       stroke=color, width=2.0)
        else
            line_svg(io, x, y - 5, x + 30, y - 5; color, width=1.4)
            diamond_svg(io, x + 15, y - 5; radius=5.0, fill=color)
        end
        text_svg(io, x + 40, y, label; size=15, anchor="start")
        x += 40 + 8.2length(label)
    end
end

function draw_method_key(io, entries; y_start=102.0, row_gap=28.0)
    x = LEFT + 10
    for (row, entry) in enumerate(entries)
        color, label, style = entry
        y = y_start + (row - 1) * row_gap
        if style == :line
            line_svg(io, x, y - 5, x + 34, y - 5; color, width=3.0)
        elseif style == :open
            line_svg(io, x, y - 5, x + 34, y - 5; color, width=2.6)
            circle_svg(
                io,
                x + 17,
                y - 5;
                radius=5.5,
                fill="none",
                stroke=color,
                width=2.2,
            )
        else
            line_svg(io, x, y - 5, x + 34, y - 5; color, width=1.5)
            diamond_svg(io, x + 17, y - 5; radius=6.0, fill=color)
        end
        text_svg(
            io,
            x + 48,
            y,
            label;
            size=20,
            anchor="start",
            weight="500",
        )
    end
end

function render_l2(
    path,
    ed,
    qmc,
    tantrg,
    source_hashes,
    qmc_sampling_label,
)
    top_values = vcat(ed.energy, qmc.energy)
    top_errors = vcat(ed.error, qmc.error)
    if !isnothing(tantrg)
        append!(top_values, tantrg.energy)
        append!(top_errors, tantrg.error)
    end
    top_scale = scales(ed.beta, top_values, top_errors)

    qmc_relative = abs.(qmc.energy .- ed.energy) ./ abs.(ed.energy)
    qmc_relative_error = qmc.error ./ abs.(ed.energy)
    relative_values = vcat(qmc_relative, qmc_relative_error)
    relative_errors = zeros(length(relative_values))
    tantrg_relative = Float64[]
    if !isnothing(tantrg)
        tantrg_relative =
            abs.(tantrg.energy .- ed.energy) ./ abs.(ed.energy)
        append!(relative_values, tantrg_relative)
        append!(relative_errors, zeros(length(tantrg_relative)))
    end
    bottom_scale = scales(
        ed.beta,
        relative_values,
        relative_errors;
        relative=true,
        logy=true,
    )

    atomic_write(path) do io
        println(io, "<svg xmlns=\"http://www.w3.org/2000/svg\" " *
                    "width=\"$(Int(WIDTH))\" height=\"$(Int(HEIGHT))\" " *
                    "viewBox=\"0 0 $(Int(WIDTH)) $(Int(HEIGHT))\">")
        println(io, "<title>2×2 OBC TFIM energy benchmark</title>")
        println(
            io,
            "<desc>Energy per site and logarithmic absolute relative " *
            "deviations for dense ED, SSE-QMC, and available tanTRG data.</desc>",
        )
        println(io, "<!-- source hashes: $(join(source_hashes, "; ")) -->")
        println(io, "<rect width=\"100%\" height=\"100%\" fill=\"#FFFFFF\"/>")
        text_svg(
            io,
            WIDTH / 2,
            38,
            "2×2 OBC TFIM energy benchmark";
            size=34,
            weight="500",
        )
        text_svg(
            io,
            WIDTH / 2,
            70,
            "J=1, h=0.5, OBC  •  βJ=1–10";
            size=21,
            color=COLOR_MUTED,
            weight="500",
        )
        method_entries = [
            (COLOR_ED, "ED — exact", :line),
            (COLOR_QMC, qmc_sampling_label, :diamond),
        ]
        if !isnothing(tantrg)
            push!(
                method_entries,
                (
                    COLOR_TANTRG,
                    "tanTRG — D=DSETTN=512; SETTN(4) + 1-site TDVP; " *
                    "cutoff 10⁻¹²",
                    :open,
                ),
            )
        end
        draw_method_key(io, method_entries; y_start=103.0, row_gap=27.0)
        draw_axes(
            io,
            top_scale,
            TOP_Y,
            TOP_HEIGHT;
            ylabel="E/N",
            custom_x_ticks=[1.0, 2.0, 4.0, 6.0, 8.0, 10.0],
        )
        draw_series(io, ed, top_scale, TOP_Y, TOP_HEIGHT;
                    color=COLOR_ED, line=true, marker=:circle, open=false,
                    width=2.2)
        draw_errorbars(io, qmc, top_scale, TOP_Y, TOP_HEIGHT;
                       color=COLOR_QMC)
        draw_series(io, qmc, top_scale, TOP_Y, TOP_HEIGHT;
                    color=COLOR_QMC, line=false, marker=:diamond)
        if !isnothing(tantrg)
            draw_series(io, tantrg, top_scale, TOP_Y, TOP_HEIGHT;
                        color=COLOR_TANTRG, line=true, marker=:circle,
                        open=true)
        end

        draw_axes(
            io,
            bottom_scale,
            BOTTOM_Y,
            BOTTOM_HEIGHT;
            ylabel="|ΔE|/|Eref| (log)",
            xlabel="βJ",
            relative=true,
            custom_x_ticks=[1.0, 2.0, 4.0, 6.0, 8.0, 10.0],
        )
        qmc_relative_series =
            Series(qmc.beta, qmc_relative, zeros(length(qmc.beta)))
        draw_series(
            io,
            qmc_relative_series,
            bottom_scale,
            BOTTOM_Y,
            BOTTOM_HEIGHT;
            color=COLOR_QMC,
            line=false,
            marker=:diamond,
        )
        draw_series(
            io,
            Series(
                qmc.beta,
                qmc_relative_error,
                zeros(length(qmc.beta)),
            ),
            bottom_scale,
            BOTTOM_Y,
            BOTTOM_HEIGHT;
            color=COLOR_QMC,
            line=true,
            marker=:none,
            width=2.0,
            dash="7 5",
        )
        if !isnothing(tantrg)
            draw_series(
                io,
                Series(tantrg.beta, tantrg_relative, tantrg.error),
                bottom_scale,
                BOTTOM_Y,
                BOTTOM_HEIGHT;
                color=COLOR_TANTRG,
                line=true,
                marker=:circle,
                open=true,
            )
        end
        text_svg(
            io,
            LEFT + PLOT_WIDTH,
            BOTTOM_Y - 17,
            "ED reference  •  dashed: QMC 1-MCSE";
            size=18,
            anchor="end",
            color=COLOR_MUTED,
            weight="500",
        )
        println(io, "</svg>")
    end

    max_qmc_relative = maximum(abs, qmc_relative)
    max_qmc_z = maximum(
        abs.((qmc.energy .- ed.energy) ./ qmc.error),
    )
    return (; max_qmc_relative, max_qmc_z)
end

function render_l4(path, qmc, tantrg, source_hashes)
    top_values = vcat(qmc.energy, tantrg.energy)
    top_errors = vcat(qmc.error, tantrg.error)
    top_scale = scales(qmc.beta, top_values, top_errors; logx=true)

    tantrg_relative =
        abs.(tantrg.energy .- qmc.energy) ./ abs.(qmc.energy)
    qmc_relative_error = qmc.error ./ abs.(qmc.energy)
    bottom_scale = scales(
        qmc.beta,
        vcat(tantrg_relative, qmc_relative_error),
        zeros(2 * length(qmc.beta));
        relative=true,
        logx=true,
        logy=true,
    )

    atomic_write(path) do io
        println(io, "<svg xmlns=\"http://www.w3.org/2000/svg\" " *
                    "width=\"$(Int(WIDTH))\" height=\"$(Int(HEIGHT))\" " *
                    "viewBox=\"0 0 $(Int(WIDTH)) $(Int(HEIGHT))\">")
        println(io, "<title>4×4 OBC TFIM energy benchmark</title>")
        println(
            io,
            "<desc>Energy per site and logarithmic absolute relative " *
            "deviation for SSE-QMC and D=512 tanTRG at exact common beta points.</desc>",
        )
        println(io, "<!-- source hashes: $(join(source_hashes, "; ")) -->")
        println(io, "<rect width=\"100%\" height=\"100%\" fill=\"#FFFFFF\"/>")
        text_svg(
            io,
            WIDTH / 2,
            38,
            "4×4 OBC TFIM energy benchmark";
            size=34,
            weight="500",
        )
        text_svg(
            io,
            WIDTH / 2,
            70,
            "J=1, h=0.5, OBC  •  25 matched β points";
            size=21,
            color=COLOR_MUTED,
            weight="500",
        )
        draw_method_key(
            io,
            [
                (
                    COLOR_QMC,
                    "SSE-QMC — 20 replicas/β; 2¹⁸ sweeps " *
                    "(2²² at high T); ±1 MCSE",
                    :diamond,
                ),
                (
                    COLOR_TANTRG,
                    "tanTRG — D=DSETTN=512; SETTN(4) + 1-site TDVP; " *
                    "cutoff 10⁻¹²",
                    :open,
                ),
            ];
            y_start=112.0,
            row_gap=30.0,
        )
        draw_axes(
            io,
            top_scale,
            TOP_Y,
            TOP_HEIGHT;
            ylabel="E/N",
        )
        draw_series(
            io,
            tantrg,
            top_scale,
            TOP_Y,
            TOP_HEIGHT;
            color=COLOR_TANTRG,
            line=true,
            marker=:circle,
            open=true,
        )
        draw_errorbars(io, qmc, top_scale, TOP_Y, TOP_HEIGHT;
                       color=COLOR_QMC)
        draw_series(
            io,
            qmc,
            top_scale,
            TOP_Y,
            TOP_HEIGHT;
            color=COLOR_QMC,
            line=false,
            marker=:diamond,
            marker_radius=5.6,
        )
        # Redraw only the tanTRG open markers above the QMC diamonds. The two
        # methods nearly coincide, so without this final layer tanTRG appears
        # to be absent even though its orange line is present.
        draw_series(
            io,
            tantrg,
            top_scale,
            TOP_Y,
            TOP_HEIGHT;
            color=COLOR_TANTRG,
            line=false,
            marker=:circle,
            open=true,
            marker_radius=7.0,
        )
        draw_axes(
            io,
            bottom_scale,
            BOTTOM_Y,
            BOTTOM_HEIGHT;
            ylabel="|ΔE|/|Eref| (log)",
            xlabel="βJ",
            relative=true,
        )
        draw_series(
            io,
            Series(
                qmc.beta,
                qmc_relative_error,
                zeros(length(qmc.beta)),
            ),
            bottom_scale,
            BOTTOM_Y,
            BOTTOM_HEIGHT;
            color=COLOR_QMC,
            line=true,
            marker=:none,
            width=2.0,
            dash="7 5",
        )
        draw_series(
            io,
            Series(tantrg.beta, tantrg_relative, tantrg.error),
            bottom_scale,
            BOTTOM_Y,
            BOTTOM_HEIGHT;
            color=COLOR_TANTRG,
            line=true,
            marker=:circle,
            open=true,
        )
        text_svg(
            io,
            LEFT + PLOT_WIDTH,
            BOTTOM_Y - 17,
            "SSE-QMC reference  •  dashed: QMC 1-MCSE";
            size=18,
            anchor="end",
            color=COLOR_MUTED,
            weight="500",
        )
        println(io, "</svg>")
    end

    max_relative = maximum(abs, tantrg_relative)
    max_qmc_z = maximum(abs.((tantrg.energy .- qmc.energy) ./ qmc.error))
    return (; max_relative, max_qmc_z)
end

function main(arguments=ARGS)
    options = parse_arguments(arguments)
    l2_hash = options.l2_sse_path == L2_ED_SSE_PATH ?
        verify_source(L2_ED_SSE_PATH, EXPECTED_L2_ED_SSE_SHA256) :
        file_sha256(options.l2_sse_path)
    l4_qmc_hash = verify_source(L4_QMC_PATH, EXPECTED_L4_QMC_SHA256)
    l4_qmc_high_t_hash =
        verify_source(L4_QMC_HIGH_T_PATH, EXPECTED_L4_QMC_HIGH_T_SHA256)
    l4_tantrg_hash =
        verify_source(L4_TANTRG_PATH, EXPECTED_L4_TANTRG_SHA256)

    ed_l2, qmc_l2 = load_l2_ed_sse(options.l2_sse_path)
    l2_qmc_label = l2_qmc_sampling_label(options.l2_sse_path)
    l2_tantrg = nothing
    l2_tantrg_hash = nothing
    if isfile(options.l2_tantrg_path)
        l2_tantrg = load_l2_tantrg(options.l2_tantrg_path, ed_l2.beta)
        l2_tantrg_hash = file_sha256(options.l2_tantrg_path)
    elseif options.require_l2_tantrg
        error(
            "required 2x2 tanTRG CSV is missing: $(options.l2_tantrg_path)",
        )
    end

    qmc_l4, tantrg_l4 = load_l4_sse_tantrg(
        L4_QMC_PATH,
        L4_QMC_HIGH_T_PATH,
        L4_TANTRG_PATH,
    )
    mkpath(options.output_directory)

    l2_filename = isnothing(l2_tantrg) ?
        "tfim-l2-ed-sse-energy-relative-deviation.svg" :
        "tfim-l2-ed-sse-tantrg-energy-relative-deviation.svg"
    l2_path = joinpath(options.output_directory, l2_filename)
    l2_sources = ["l2-ed-sse=$l2_hash"]
    !isnothing(l2_tantrg_hash) &&
        push!(l2_sources, "l2-tantrg=$l2_tantrg_hash")
    l2_summary = render_l2(
        l2_path,
        ed_l2,
        qmc_l2,
        l2_tantrg,
        l2_sources,
        l2_qmc_label,
    )

    l4_path = joinpath(
        options.output_directory,
        "tfim-l4-sse-tantrg-energy-relative-deviation.svg",
    )
    l4_summary = render_l4(
        l4_path,
        qmc_l4,
        tantrg_l4,
        [
            "l4-qmc=$l4_qmc_hash",
            "l4-qmc-high-t=$l4_qmc_high_t_hash",
            "l4-tantrg=$l4_tantrg_hash",
        ],
    )

    println("WROTE_L2=$l2_path")
    println("WROTE_L4=$l4_path")
    println(
        "L2_QMC_MAX_ABS_RELATIVE_DEVIATION=",
        l2_summary.max_qmc_relative,
    )
    println("L2_QMC_MAX_ABS_Z=", l2_summary.max_qmc_z)
    println(
        "L4_TANTRG_MAX_ABS_RELATIVE_DEVIATION=",
        l4_summary.max_relative,
    )
    println("L4_TANTRG_MAX_ABS_QMC_Z=", l4_summary.max_qmc_z)
    if isnothing(l2_tantrg)
        println(
            stderr,
            "NOTICE: 2x2 tanTRG data were not supplied; the 2x2 SVG is " *
            "explicitly ED+SSE-only.",
        )
    end
    return nothing
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main()
end
