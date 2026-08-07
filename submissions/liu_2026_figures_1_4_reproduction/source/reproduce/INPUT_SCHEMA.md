# Figure 2–4 collaborator input schema

`input.in` is JSON and uses schema version 2. It has two independent parts:

- `panels`: measured data used to fit or plot Figures 2–4;
- `physical_model`: atomic, optical, magnetic, geometric, and microscopic
  inputs needed to extend the effective model.

Paths are resolved relative to `input.in`. A data slot accepts:

```json
{
  "source": "csv",
  "path": "experimental_data/example.csv",
  "provenance": "measured on 2026-07-30; calibration notebook ABC"
}
```

Use `"source": "inline"` with a `rows` list for small data sets. Keep
`"source": "unavailable"` when a quantity has not been supplied. Do not put
placeholder numbers into an unavailable slot.

## Physical metadata

`physical_model.atom` records the isotope and the explicit qubit,
intermediate, and Rydberg states. Each state requires a unique `label`;
collaborators may add `n`, `nu`, `L`, `J`, `F`, `m_J`, `m_F`,
`configuration`, `term`, and a provenance string when those quantum numbers
are meaningful.

`physical_model.laser_beams` is a list, so direct one-photon and multi-beam
two-photon schemes use the same interface. Record wavelength, detuning, Rabi
frequency, propagation direction, polarization components, and provenance.
For this paper the atoms see one direct 302 nm gate beam; the 1971 nm and
1560 nm lasers are frequency-conversion sources, not two atomic transitions.

`physical_model.magnetic_field` and `physical_model.geometry` hold measured
field/axis and atom-spacing/orientation metadata. Unknown vector information
must remain `null`.

## Microscopic CSV contracts

| Slot | Required columns |
|---|---|
| `pulse_waveform` | `time_us`, `amplitude_rad_per_us`, `phase_rad` |
| `zeeman_calibration` | `state_label`, `field_gauss`, `shift_mhz`, `uncertainty_mhz` |
| `polarization_calibration` | `beam_id`, `component`, `relative_amplitude`, `phase_rad`, `uncertainty` |
| `mqdt_pair_states` | `distance_um`, `pair_state_id`, `energy_mhz`, `product_state`, `overlap_real`, `overlap_imag` |
| `distance_samples` | `sample_id`, `distance_um`, `polar_angle_rad`, `azimuth_rad` |
| `decay_branching` | `initial_state`, `final_state`, `rate_per_us` |
| `laser_phase_noise_psd` | `frequency_mhz`, `psd_rad2_per_mhz` |
| `laser_amplitude_noise_psd` | `frequency_mhz`, `psd_fraction2_per_mhz` |

The manifest runner validates file existence and column names, then writes
`physical_model_inputs.json` with supplied/missing counts and resolved paths.

## Consumption boundary

The present Figure 3 Hessian remains the paper's ten-state perfect-blockade
model. Schema-v2 microscopic inputs are validated and preserved, but are not
silently inserted into that Hamiltonian. A future full-model stage must
explicitly consume the supplied MQDT, decay, noise, field, polarization, and
geometry data and record that choice in its output provenance.

Run the audit with:

```bash
.venv/bin/python liu_2026_experimental_analysis.py \
  --input-in input.in \
  --output-dir /tmp/liu-input-audit
```
