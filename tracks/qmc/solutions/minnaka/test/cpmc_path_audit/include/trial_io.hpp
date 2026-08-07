#pragma once

#include "trial.hpp"

#include <cstddef>
#include <string>

namespace audit {

Matrix read_real_orbitals(const std::string& path, std::size_t rows,
                          std::size_t cols);
void write_real_orbitals(const std::string& path,
                         const Matrix& orbitals);
double orthonormality_residual(const Matrix& orbitals);
double particle_hole_projector_residual(const Matrix& up,
                                        const Matrix& down,
                                        const HubbardModel& model);
double orient_overlap_positive(Matrix& trial, const Matrix& initial);

}  // namespace audit
