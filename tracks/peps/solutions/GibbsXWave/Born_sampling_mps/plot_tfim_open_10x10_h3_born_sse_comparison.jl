#!/usr/bin/env julia

const INPUT_CSV = joinpath(
    @__DIR__,
    "tfim_open_10x10_h3_born_sse_plot_data.csv",
)
const DEFAULT_OUTPUT_PNG = joinpath(
    @__DIR__,
    "tfim_open_10x10_h3_born_sse_comparison.png",
)

const SERIES_STYLES = [
    (
        label="stoMPS",
        plot_label="stoMPS",
        color="#7B3294",
        point_type=9,
        direct_stomps=true,
    ),
    (
        label="tanTRG+stoMPS, T0=4",
        plot_label="tanTRG+stoMPS, {/\"Times New Roman\":Italic β}_{0} = 0.25",
        color="#08306B",
        point_type=5,
        direct_stomps=false,
    ),
    (
        label="tanTRG+stoMPS, T0=2",
        plot_label="tanTRG+stoMPS, {/\"Times New Roman\":Italic β}_{0} = 0.5",
        color="#2171B5",
        point_type=7,
        direct_stomps=false,
    ),
    (
        label="tanTRG+stoMPS, T0=1",
        plot_label="tanTRG+stoMPS, {/\"Times New Roman\":Italic β}_{0} = 1",
        color="#6BAED6",
        point_type=11,
        direct_stomps=false,
    ),
    (
        label="tanTRG",
        plot_label="tanTRG",
        color="#D62728",
        point_type=13,
        direct_stomps=false,
    ),
]

function usage()
    println(
        "Usage: julia ",
        basename(@__FILE__),
        " [OUTPUT_PNG]",
    )
end

function parse_csv_line(line::String)
    fields = String[]
    buffer = IOBuffer()
    quoted = false
    index = firstindex(line)
    while index <= lastindex(line)
        character = line[index]
        if character == '"'
            next_index = nextind(line, index)
            if quoted && next_index <= lastindex(line) && line[next_index] == '"'
                write(buffer, '"')
                index = next_index
            else
                quoted = !quoted
            end
        elseif character == ',' && !quoted
            push!(fields, String(take!(buffer)))
        else
            write(buffer, character)
        end
        index = nextind(line, index)
    end
    quoted && error("Unterminated quoted field in CSV row")
    push!(fields, String(take!(buffer)))
    return fields
end

function read_plot_table(path::String)
    isfile(path) || error("Plot-data CSV does not exist: $path")
    lines = filter(line -> !isempty(strip(line)), readlines(path))
    length(lines) >= 2 || error("Plot-data CSV has no data rows: $path")
    header = parse_csv_line(first(lines))
    length(unique(header)) == length(header) || error(
        "Plot-data CSV has duplicate column names: $path",
    )
    columns = Dict(name => index for (index, name) in enumerate(header))
    required_columns = (
        "series",
        "plot_record_kind",
        "beta",
        "temperature",
        "method",
        "energy_per_site",
        "energy_error_per_site",
        "energy_error_available",
        "absolute_difference_from_sse",
        "combined_statistical_error",
        "specific_heat_per_site",
        "specific_heat_error_per_site",
        "specific_heat_error_available",
        "contributes_to_energy_panel",
        "contributes_to_specific_heat_panel",
        "contributes_to_absolute_error_panel",
    )
    for name in required_columns
        haskey(columns, name) || error("Missing CSV column '$name' in $path")
    end
    rows = Vector{Vector{String}}()
    for (row_index, line) in enumerate(lines[2:end])
        fields = parse_csv_line(line)
        length(fields) == length(header) || error(
            "CSV row $(row_index + 1) has $(length(fields)) fields; " *
            "expected $(length(header))",
        )
        push!(rows, fields)
    end
    return (; columns, rows)
end

value(row, columns, name::String) = row[columns[name]]

function parse_required_float(row, columns, name::String)
    text = value(row, columns, name)
    isempty(text) && error("Required numeric field '$name' is blank")
    result = parse(Float64, text)
    isfinite(result) || error("Field '$name' contains NaN or Inf")
    return result
end

function parse_optional_float(row, columns, name::String)
    text = value(row, columns, name)
    isempty(text) && return NaN
    result = parse(Float64, text)
    isfinite(result) || error("Field '$name' contains NaN or Inf")
    return result
end

function parse_boolean(row, columns, name::String)
    text = lowercase(value(row, columns, name))
    text == "true" && return true
    text == "false" && return false
    error("Field '$name' is not a Boolean: $(repr(text))")
end

function matching_rows(table, series::String, record_kind::String)
    columns = table.columns
    return filter(
        row -> value(row, columns, "series") == series &&
            value(row, columns, "plot_record_kind") == record_kind,
        table.rows,
    )
end

function validate_beta_order(rows, columns, series::String)
    beta = [parse_required_float(row, columns, "beta") for row in rows]
    isempty(beta) && error("Series '$series' has no energy data")
    all(diff(beta) .> 0) || error(
        "Series '$series' beta grid is not strictly increasing",
    )
end

function gnuplot_quote(text::AbstractString)
    return replace(replace(text, "\\" => "\\\\"), "'" => "\\'")
end

function write_data_block(io, name::String, rows)
    println(io, "\$$name << EOD")
    for row in rows
        isnothing(row) ? println(io) : println(io, join(row, '\t'))
    end
    println(io, "EOD")
end

function build_plot_data(table)
    columns = table.columns
    sse_rows = matching_rows(table, "SSE", "data_knot")
    validate_beta_order(sse_rows, columns, "SSE")
    all(parse_boolean(row, columns, "contributes_to_energy_panel") for row in
        sse_rows) || error("Every SSE row must contribute to the energy panel")

    sse = [
        (
            parse_required_float(row, columns, "temperature"),
            parse_required_float(row, columns, "energy_per_site"),
            parse_required_float(row, columns, "energy_error_per_site"),
        ) for row in sse_rows
    ]
    sse_specific_heat = [
        (
            parse_required_float(row, columns, "temperature"),
            parse_required_float(row, columns, "specific_heat_per_site"),
            parse_required_float(row, columns, "specific_heat_error_per_site"),
        ) for row in sse_rows
    ]

    series = NamedTuple[]
    all_absolute_differences = Float64[]
    for style in SERIES_STYLES
        energy_rows = matching_rows(table, style.label, "data_knot")
        validate_beta_order(energy_rows, columns, style.label)
        energy = [
            (
                parse_required_float(row, columns, "temperature"),
                parse_required_float(row, columns, "energy_per_site"),
                parse_boolean(row, columns, "energy_error_available") ?
                    parse_required_float(row, columns, "energy_error_per_site") :
                    NaN,
            ) for row in energy_rows
        ]
        energy_error_available = [
            parse_boolean(row, columns, "energy_error_available") for
            row in energy_rows
        ]

        heat_rows = matching_rows(table, style.label, "specific_heat_interval")
        isempty(heat_rows) && error(
            "Series '$(style.label)' has no specific-heat intervals",
        )
        specific_heat = Any[]
        heat_error_available = Bool[]
        previous_segment = nothing
        for row in heat_rows
            parse_boolean(
                row,
                columns,
                "contributes_to_specific_heat_panel",
            ) || error("Specific-heat row is not marked for plotting")
            segment = value(row, columns, "method")
            if !isnothing(previous_segment) && segment != previous_segment
                push!(specific_heat, nothing)
            end
            error_available = parse_boolean(
                row,
                columns,
                "specific_heat_error_available",
            )
            push!(specific_heat, (
                parse_required_float(row, columns, "temperature"),
                parse_required_float(row, columns, "specific_heat_per_site"),
                error_available ? parse_required_float(
                    row,
                    columns,
                    "specific_heat_error_per_site",
                ) : NaN,
            ))
            push!(heat_error_available, error_available)
            previous_segment = segment
        end

        residual_rows = filter(
            row -> parse_boolean(
                row,
                columns,
                "contributes_to_absolute_error_panel",
            ),
            energy_rows,
        )
        isempty(residual_rows) && error(
            "Series '$(style.label)' has no SSE comparison points",
        )
        residual = NamedTuple[]
        for row in residual_rows
            difference = parse_required_float(
                row,
                columns,
                "absolute_difference_from_sse",
            )
            difference > 0 || error(
                "Absolute differences must be positive for the log axis",
            )
            push!(all_absolute_differences, difference)
            uncertainty_available = parse_boolean(
                row,
                columns,
                "energy_error_available",
            )
            combined_error = uncertainty_available ? parse_required_float(
                row,
                columns,
                "combined_statistical_error",
            ) : NaN
            push!(residual, (
                temperature=parse_required_float(row, columns, "temperature"),
                difference,
                combined_error,
                uncertainty_available,
            ))
        end

        push!(series, merge(style, (;
            energy,
            energy_error_available,
            specific_heat,
            heat_error_available,
            residual,
        )))
    end
    isempty(all_absolute_differences) && error("No absolute differences found")
    return (;
        sse,
        sse_specific_heat,
        sse_maximum_beta=maximum(
            parse_required_float(row, columns, "beta") for row in sse_rows
        ),
        series,
        absolute_difference_minimum=minimum(all_absolute_differences),
        absolute_difference_maximum=maximum(all_absolute_differences),
    )
end

function plot_comparison(path::String, data)
    Sys.which("gnuplot") === nothing && error(
        "gnuplot is required but was not found on PATH",
    )
    mkpath(dirname(path))
    temperature_minimum = inv(data.sse_maximum_beta) / 1.15
    temperature_maximum = 100.0
    logarithmic_errorbar_floor = data.absolute_difference_minimum / 5

    open(`gnuplot`, "w") do gnuplot
        println(
            gnuplot,
            "set terminal pngcairo size 2300,2300 enhanced " *
            "font 'Times New Roman,34' linewidth 2",
        )
        println(gnuplot, "set output '$(gnuplot_quote(path))'")
        write_data_block(gnuplot, "sse", data.sse)
        write_data_block(
            gnuplot,
            "sse_specific_heat",
            data.sse_specific_heat,
        )
        for (series_index, result) in enumerate(data.series)
            write_data_block(
                gnuplot,
                "series_$series_index",
                result.energy,
            )
            write_data_block(
                gnuplot,
                "specific_heat_$series_index",
                result.specific_heat,
            )
            write_data_block(gnuplot, "residual_$series_index", [
                (
                    row.temperature,
                    row.difference,
                    row.uncertainty_available ? max(
                        row.difference - row.combined_error,
                        logarithmic_errorbar_floor,
                    ) : NaN,
                    row.uncertainty_available ?
                        row.difference + row.combined_error : NaN,
                ) for row in result.residual
            ])
        end

        println(gnuplot, "set multiplot")
        println(gnuplot, "set lmargin 13")
        println(gnuplot, "set rmargin 4")
        println(gnuplot, "set logscale x")
        println(
            gnuplot,
            "set xrange [$temperature_minimum:$temperature_maximum]",
        )
        println(gnuplot, "set border linewidth 2")
        println(
            gnuplot,
            "set grid back linewidth 1.5 linecolor rgb '#D9D9D9'",
        )
        println(gnuplot, "set tics in scale 1.25")
        println(gnuplot, "set pointsize 1.6")
        println(gnuplot, "set bars 1.4")
        println(
            gnuplot,
            "set key left top invert font 'Times New Roman,34' spacing 1.25",
        )

        println(gnuplot, "set origin 0,0.62")
        println(gnuplot, "set size 1,0.38")
        println(
            gnuplot,
            "set title 'Open 10×10 TFIM, {/\"Times New Roman\":Italic J} = 1, " *
            "{/\"Times New Roman\":Italic h} = 3' offset 0,-0.3",
        )
        println(
            gnuplot,
            "set ylabel '{/\"Times New Roman\":Italic E}' " *
            "font 'Times New Roman:Italic,38' offset 1,0",
        )
        println(gnuplot, "unset xlabel")
        println(gnuplot, "set format x ''")
        top_commands = String[]
        for series_index in reverse(eachindex(data.series))
            result = data.series[series_index]
            line_style = result.direct_stomps ? "dashtype 2" : "dashtype 1"
            push!(
                top_commands,
                "\$series_$series_index using 1:2 with linespoints " *
                "linewidth 3.4 $line_style pointtype $(result.point_type) " *
                "pointsize 1.5 linecolor rgb '$(result.color)' " *
                "title '$(gnuplot_quote(result.plot_label))'",
            )
            any(result.energy_error_available) && push!(
                top_commands,
                "\$series_$series_index using 1:2:3 with yerrorbars " *
                "linewidth 2.2 pointtype $(result.point_type) pointsize 1.25 " *
                "linecolor rgb '$(result.color)' notitle",
            )
        end
        tantrg_index = only(findall(
            result -> result.label == "tanTRG",
            data.series,
        ))
        tantrg_result = data.series[tantrg_index]
        push!(
            top_commands,
            "\$series_$tantrg_index using 1:2 with linespoints " *
            "linewidth 4.0 dashtype 1 pointtype $(tantrg_result.point_type) " *
            "pointsize 1.6 linecolor rgb '$(tantrg_result.color)' notitle",
        )
        push!(
            top_commands,
            "\$sse using 1:2:3 with yerrorbars linewidth 2.4 " *
            "pointtype 7 pointsize 1.55 linecolor rgb '#000000' title 'SSE'",
        )
        println(gnuplot, "plot " * join(top_commands, ", \\\n     "))

        println(gnuplot, "set origin 0,0")
        println(gnuplot, "set size 1,0.31")
        println(gnuplot, "unset title")
        println(gnuplot, "unset key")
        println(
            gnuplot,
            "set xlabel '{/\"Times New Roman\":Italic T/J}' " *
            "font 'Times New Roman:Italic,38' offset 0,0.4",
        )
        println(gnuplot, "set format x '%g'")
        println(gnuplot, "unset logscale y")
        println(gnuplot, "set format y '%g'")
        println(gnuplot, "set yrange [*:*]")
        println(
            gnuplot,
            "set ylabel '{/\"Times New Roman\":Italic C}' " *
            "font 'Times New Roman:Italic,38' offset 1,0",
        )
        specific_heat_commands = String[]
        for series_index in reverse(eachindex(data.series))
            result = data.series[series_index]
            line_style = result.direct_stomps ? "dashtype 2" : "dashtype 1"
            push!(
                specific_heat_commands,
                "\$specific_heat_$series_index using 1:2 with linespoints " *
                "linewidth 3.4 $line_style pointtype $(result.point_type) " *
                "pointsize 1.5 linecolor rgb '$(result.color)' notitle",
            )
            any(result.heat_error_available) && push!(
                specific_heat_commands,
                "\$specific_heat_$series_index using 1:2:3 with yerrorbars " *
                "linewidth 2.2 pointtype $(result.point_type) pointsize 1.25 " *
                "linecolor rgb '$(result.color)' notitle",
            )
        end
        push!(
            specific_heat_commands,
            "\$specific_heat_$tantrg_index using 1:2 with linespoints " *
            "linewidth 4.0 dashtype 1 pointtype $(tantrg_result.point_type) " *
            "pointsize 1.6 linecolor rgb '$(tantrg_result.color)' notitle",
        )
        push!(
            specific_heat_commands,
            "\$sse_specific_heat using 1:2:3 with yerrorbars linewidth 2.4 " *
            "pointtype 7 pointsize 1.55 linecolor rgb '#000000' notitle",
        )
        println(
            gnuplot,
            "plot " * join(specific_heat_commands, ", \\\n     "),
        )

        println(gnuplot, "set origin 0,0.31")
        println(gnuplot, "set size 1,0.31")
        println(gnuplot, "set logscale y")
        println(gnuplot, "set format y '10^{%L}'")
        println(
            gnuplot,
            "set yrange [$(data.absolute_difference_minimum / 1.8):" *
            "$(data.absolute_difference_maximum * 1.8)]",
        )
        println(gnuplot, "unset xlabel")
        println(gnuplot, "set format x ''")
        println(
            gnuplot,
            "set ylabel '{/\"Times New Roman\":Italic δ}' " *
            "font 'Times New Roman:Italic,38' offset 1,0",
        )
        residual_commands = String[]
        for (series_index, result) in enumerate(data.series)
            line_style = result.direct_stomps ? "dashtype 2" : "dashtype 1"
            push!(
                residual_commands,
                "\$residual_$series_index using 1:2 with linespoints " *
                "linewidth 3.4 $line_style pointtype $(result.point_type) " *
                "pointsize 1.5 linecolor rgb '$(result.color)' notitle",
            )
            any(result.energy_error_available) && push!(
                residual_commands,
                "\$residual_$series_index using 1:2:3:4 with yerrorbars " *
                "linewidth 2.2 pointtype $(result.point_type) pointsize 1.25 " *
                "linecolor rgb '$(result.color)' notitle",
            )
        end
        println(gnuplot, "plot " * join(residual_commands, ", \\\n     "))

        println(gnuplot, "unset logscale y")
        println(gnuplot, "unset multiplot")
    end
    isfile(path) && filesize(path) > 0 || error(
        "gnuplot did not create $path",
    )
    return path
end

if any(argument -> argument in ("-h", "--help"), ARGS)
    usage()
    exit()
end
length(ARGS) <= 1 || begin
    usage()
    error("Expected at most one positional argument")
end

output_png = abspath(get(ARGS, 1, DEFAULT_OUTPUT_PNG))
table = read_plot_table(INPUT_CSV)
data = build_plot_data(table)
plot_comparison(output_png, data)
println("Comparison plot: $output_png")
