module FloquetSpinBoson

include("config.jl")
include("model.jl")
include("bath.jl")
include("uniform_if.jl")
include("checkpoint.jl")
include("augmented_step.jl")
include("floquet_operator.jl")
include("steady_state.jl")
include("correlations.jl")
include("heat_current.jl")
include("convergence.jl")
include("reference_data.jl")
include("redfield_magnus.jl")
include("diagnostics.jl")

export RunConfig, Fig3Config, Fig5Config, period_grid,
       SpinBosonModel, SIGMA_X, SIGMA_Z,
       drive_hamiltonian, system_hamiltonian, bath_correlation, bath_gamma,
       UniformIFAdapter, UniformIFBuildSettings, adapt_uniform_pt,
       installed_uniformtempo_revision, uniform_if_metadata, uniform_if_key,
       uniform_if_build_settings, build_or_load_uniform_if,
       uniform_if_cache_path, load_or_build_uniform_if, atomic_save,
       AugmentedLayout, composite_index, StepOperator, StepWorkspace,
       apply_step!, apply_step_adjoint!, FloquetOperator, apply_period!,
       apply_period_adjoint!, precompute_half_step_channels,
       estimated_dense_bytes, dense_floquet, FloquetLinearOperator,
       FloquetEigenResult, FloquetWarmStart, validate_warm_start,
       solve_floquet_steady_state, normalize_floquet_trace,
       reduce_system_state, micromotion_states,
       InsertionConvention, CorrelationCheckpoint,
       save_correlation_checkpoint, load_correlation_checkpoint,
       floquet_correlation_serial!, floquet_correlation_threaded!,
       correlation_diagnostics, periodic_autocorrelation_fft,
       periodic_autocorrelation_direct, decompose_correlation,
       spectral_density, continuous_current_fft, continuous_current_direct!,
       DeltaPeak, delta_peak_weights, group_frequencies_by_dt,
       integrated_current, period_averaged_power, pending_fig5_points,
       fig5_config_hash,
       REQUIRED_CONVERGENCE_AXES, require_convergence_evidence,
       choose_compute_route, estimate_resources,
       run_fig3, run_fig5,
       floquet_eigen_diagnostics,
       load_reference_curve, fig3_reference_grid, load_fig3_reference,
       fig3_reference_path, fig5_reference_grid, load_fig5_reference,
       fig5_reference_path, redfield_magnus!, redfield_magnus_paper_formula,
       run_fig2, parse_exact_baseline, render_refreshed_errors

end
