#!/usr/bin/env julia

const ROOT = normpath(joinpath(@__DIR__, ".."))
include(joinpath(@__DIR__, "reproduce_fig2.jl"))

println("Benchmark uses the selected strict Fig. 2 configuration; output records no IF metrics unless an IF backend is supplied.")
