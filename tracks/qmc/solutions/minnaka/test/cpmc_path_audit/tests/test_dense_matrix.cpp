#include "dense_matrix.hpp"
#include "test_common.hpp"

#include <vector>

using audit::Matrix;

int main() {
    return run_test_main([] {
        Matrix a(2, 2, {2.0, 1.0, 1.0, 2.0});
        require_near(audit::determinant(a), 3.0, 1e-12, "determinant");

        const Matrix inv = audit::inverse(a);
        const Matrix identity = audit::multiply(a, inv);
        require_near(identity(0, 0), 1.0, 1e-12, "inverse (0,0)");
        require_near(identity(1, 1), 1.0, 1e-12, "inverse (1,1)");
        require_near(identity(0, 1), 0.0, 1e-12, "inverse (0,1)");

        const Matrix right(2, 2, {3.0, -1.0, 2.0, 4.0});
        const Matrix solution = audit::solve(a, right);
        require_true(
            audit::max_abs_difference(
                audit::multiply(a, solution), right
            ) < 1e-12,
            "LU solve reconstructs the right-hand side"
        );
        bool singular_rejected = false;
        try {
            (void)audit::solve(
                Matrix(2, 2, {1.0, 2.0, 2.0, 4.0}), right
            );
        } catch (const std::runtime_error&) {
            singular_rejected = true;
        }
        require_true(singular_rejected, "singular solve must be rejected");

        const auto [values, vectors] = audit::symmetric_eigh(a);
        require_near(values.at(0), 1.0, 1e-12, "lowest eigenvalue");
        require_near(values.at(1), 3.0, 1e-12, "highest eigenvalue");
        Matrix eigenvalue_matrix(2, 2,
                                 {values.at(0), 0.0, 0.0, values.at(1)});
        const Matrix reconstructed = audit::multiply(
            audit::multiply(vectors, eigenvalue_matrix),
            audit::transpose(vectors));
        require_true(audit::max_abs_difference(reconstructed, a) < 1e-12,
                     "eigendecomposition reconstructs the matrix");

        Matrix nonsymmetric_eigenbasis(
            3, 3, {2.0, 1.0, 0.2, 1.0, 3.0, 0.7, 0.2, 0.7, 5.0});
        const auto [values3, vectors3] =
            audit::symmetric_eigh(nonsymmetric_eigenbasis);
        Matrix diagonal3(3, 3);
        for (std::size_t i = 0; i < 3; ++i) {
            diagonal3(i, i) = values3.at(i);
        }
        const Matrix reconstructed3 = audit::multiply(
            audit::multiply(vectors3, diagonal3),
            audit::transpose(vectors3));
        require_true(
            audit::max_abs_difference(reconstructed3,
                                      nonsymmetric_eigenbasis) < 1e-12,
            "general eigendecomposition reconstructs the matrix");

        Matrix diagonal(2, 2, {1.0, 0.0, 0.0, 2.0});
        const Matrix exponential =
            audit::symmetric_exponential(diagonal, -0.5);
        require_near(exponential(0, 0), std::exp(-0.5), 1e-12,
                     "matrix exponential first value");
        require_near(exponential(1, 1), std::exp(-1.0), 1e-12,
                     "matrix exponential second value");

        const Matrix rectangular(
            4, 2, {1.0, 20.0, -1.0, 0.5, 3.0, -2.0, 0.25, 1.5});
        const auto qr = audit::thin_qr(rectangular);
        require_true(
            qr.pivoted_column_by_position ==
                std::vector<std::size_t>({1, 0}),
            "thin QR uses column pivoting");
        require_true(
            qr.permutation_sign == -1,
            "thin QR records the pivot permutation sign");
        const auto pivoted = audit::multiply(qr.q, qr.r);
        Matrix qr_reconstructed(rectangular.rows(), rectangular.cols());
        for (std::size_t position = 0;
             position < qr.pivoted_column_by_position.size(); ++position) {
            const std::size_t original =
                qr.pivoted_column_by_position.at(position);
            for (std::size_t row = 0; row < rectangular.rows(); ++row) {
                qr_reconstructed(row, original) = pivoted(row, position);
            }
        }
        require_true(
            audit::max_abs_difference(
                qr_reconstructed, rectangular) < 1e-12,
            "pivoted thin QR reconstruction");
        const auto qtq =
            audit::multiply(audit::transpose(qr.q), qr.q);
        require_true(
            audit::max_abs_difference(qtq, audit::identity(2)) < 1e-12,
            "thin QR orthonormal columns");

        bool rejected = false;
        try {
            (void)audit::multiply(Matrix(2, 3), Matrix(2, 2));
        } catch (const std::invalid_argument&) {
            rejected = true;
        }
        require_true(rejected, "dimension mismatch must be rejected");
    });
}
