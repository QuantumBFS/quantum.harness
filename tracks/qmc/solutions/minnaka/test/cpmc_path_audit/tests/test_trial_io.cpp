#include "trial_io.hpp"
#include "test_common.hpp"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <limits>
#include <string>

namespace {

class TempDir {
public:
    TempDir() {
        path_ = std::filesystem::temp_directory_path() /
                ("trial-io-" + std::to_string(
                    static_cast<unsigned long long>(
                        std::filesystem::file_time_type::clock::now()
                            .time_since_epoch()
                            .count())));
        std::filesystem::create_directories(path_);
    }
    ~TempDir() { std::filesystem::remove_all(path_); }
    const std::filesystem::path& path() const { return path_; }

private:
    std::filesystem::path path_;
};

audit::Matrix canonical_orbitals() {
    audit::Matrix matrix(4, 2);
    const double scale = 0.5;
    for (std::size_t site = 0; site < 4; ++site) {
        const std::size_t x = site % 2;
        matrix(site, 0) = scale;
        matrix(site, 1) = scale * (x == 0 ? 1.0 : -1.0);
    }
    return matrix;
}

template <typename Function>
void require_throws(const Function& function, const std::string& message) {
    bool threw = false;
    try {
        function();
    } catch (const std::exception&) {
        threw = true;
    }
    require_true(threw, message);
}

}  // namespace

int main() {
    return run_test_main([] {
        TempDir temp;
        const auto orbitals = canonical_orbitals();
        const auto path = temp.path() / "orbitals.dat";
        audit::write_real_orbitals(path.string(), orbitals);
        const auto roundtrip =
            audit::read_real_orbitals(path.string(), 4, 2);
        require_true(audit::max_abs_difference(orbitals, roundtrip) <
                         1.0e-16,
                     "orbital ASCII roundtrip");
        require_true(audit::orthonormality_residual(roundtrip) < 1.0e-12,
                     "orthonormality residual");

        {
            std::ofstream output(temp.path() / "extra.dat");
            output << "4 2\n";
            for (double value : orbitals.values()) {
                output << value << '\n';
            }
            output << "3.0\n";
        }
        require_throws(
            [&] {
                (void)audit::read_real_orbitals(
                    (temp.path() / "extra.dat").string(), 4, 2);
            },
            "extra values are rejected");

        {
            std::ofstream output(temp.path() / "nan.dat");
            output << "4 2\n";
            for (std::size_t index = 0; index < orbitals.values().size();
                 ++index) {
                output << (index == 3 ? "nan" : "0.0") << '\n';
            }
        }
        require_throws(
            [&] {
                (void)audit::read_real_orbitals(
                    (temp.path() / "nan.dat").string(), 4, 2);
            },
            "nonfinite values are rejected");

        audit::Matrix flipped = orbitals;
        for (std::size_t row = 0; row < flipped.rows(); ++row) {
            flipped(row, flipped.cols() - 1) *= -1.0;
        }
        const double overlap =
            audit::orient_overlap_positive(flipped, orbitals);
        require_true(overlap > 1.0e-10, "oriented overlap is positive");
        require_true(audit::max_abs_difference(flipped, orbitals) <
                         1.0e-15,
                     "orientation only flips the last column");

        const auto model =
            audit::HubbardModel::square_periodic(2, 2, 1.0, 4.0, 0.05, 2, 2);
        audit::Matrix down(4, 2);
        const audit::Matrix projector =
            audit::multiply(orbitals, audit::transpose(orbitals));
        const audit::Matrix complement =
            audit::identity(4);
        audit::Matrix down_projector(4, 4);
        for (std::size_t row = 0; row < 4; ++row) {
            for (std::size_t col = 0; col < 4; ++col) {
                down_projector(row, col) =
                    model.sublattice(row) * model.sublattice(col) *
                    (complement(row, col) - projector(row, col));
            }
        }
        const auto [values, vectors] =
            audit::symmetric_eigh(down_projector);
        (void)values;
        for (std::size_t row = 0; row < 4; ++row) {
            for (std::size_t col = 0; col < 2; ++col) {
                down(row, col) = vectors(row, 2 + col);
            }
        }
        require_true(audit::particle_hole_projector_residual(
                         orbitals, down, model) < 1.0e-10,
                     "particle-hole projector residual");
    });
}
