#include <Eigen/Dense>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include "mkl.h"

using Matrix = Eigen::Matrix<double, Eigen::Dynamic, Eigen::Dynamic, Eigen::ColMajor>;

struct Arguments {
    int size = 0;
    std::uint64_t seed = 0;
    double p = 0.0;
    double coupling = 0.0;
    int qr_interval = 0;
    std::uint64_t burn_in = 0;
    std::uint64_t measurement = 0;
    std::uint64_t output_block = 0;
    int parity = 1;
    std::string output;
};

Arguments parse_arguments(int argc, char **argv) {
    if (argc != 11) {
        throw std::runtime_error(
            "usage: rbim_stream L SEED P K QR BURN MEASURE BLOCK PARITY OUTPUT"
        );
    }
    Arguments result;
    result.size = std::stoi(argv[1]);
    result.seed = std::stoull(argv[2]);
    result.p = std::stod(argv[3]);
    result.coupling = std::stod(argv[4]);
    result.qr_interval = std::stoi(argv[5]);
    result.burn_in = std::stoull(argv[6]);
    result.measurement = std::stoull(argv[7]);
    result.output_block = std::stoull(argv[8]);
    result.parity = std::stoi(argv[9]);
    result.output = argv[10];
    if (
        result.size < 2 || result.qr_interval < 1
        || result.burn_in % static_cast<std::uint64_t>(result.qr_interval) != 0
        || result.measurement % result.output_block != 0
        || result.output_block % static_cast<std::uint64_t>(result.qr_interval) != 0
        || (result.parity != 1 && result.parity != -1)
    ) {
        throw std::runtime_error("invalid or unaligned arguments");
    }
    return result;
}

Matrix free_state(int size) {
    Matrix state = Matrix::Zero(2 * size, size);
    for (int index = 0; index < size; ++index) {
        state(2 * index, index) = std::sqrt(2.0);
        state(2 * index + 1, index) = std::sqrt(2.0);
    }
    return state;
}

void apply_vertical(
    Matrix &state,
    const std::vector<double> &bonds,
    double coupling,
    int parity
) {
    const int size = state.cols();
    const double diagonal = std::cosh(2.0 * coupling);
    const double sinh_value = std::sinh(2.0 * coupling);
    for (int index = 0; index < size - 1; ++index) {
        const Eigen::RowVectorXd first = state.row(2 * index + 1);
        const Eigen::RowVectorXd second = state.row(2 * index + 2);
        const double off = -sinh_value * bonds[static_cast<std::size_t>(index)];
        state.row(2 * index + 1) = diagonal * first + off * second;
        state.row(2 * index + 2) = off * first + diagonal * second;
    }
    const Eigen::RowVectorXd first = state.row(0);
    const Eigen::RowVectorXd last = state.row(2 * size - 1);
    const double off = (
        static_cast<double>(parity) * sinh_value
        * bonds[static_cast<std::size_t>(size - 1)]
    );
    state.row(0) = diagonal * first + off * last;
    state.row(2 * size - 1) = off * first + diagonal * last;
}

void apply_horizontal(
    Matrix &state,
    const std::vector<double> &bonds,
    double coupling
) {
    const int size = state.cols();
    const double dual = std::atanh(std::exp(-2.0 * coupling));
    const double cosh_value = std::cosh(2.0 * dual);
    const double sinh_value = std::sinh(2.0 * dual);
    for (int index = 0; index < size; ++index) {
        const Eigen::RowVectorXd first = state.row(2 * index);
        const Eigen::RowVectorXd second = state.row(2 * index + 1);
        const double sign = bonds[static_cast<std::size_t>(index)];
        const double diagonal = cosh_value * sign;
        const double off = sinh_value * sign;
        state.row(2 * index) = diagonal * first + off * second;
        state.row(2 * index + 1) = off * first + diagonal * second;
    }
}

double stabilize(Matrix &state, double &maximum_orthogonality, std::uint64_t count) {
    const lapack_int rows = static_cast<lapack_int>(state.rows());
    const lapack_int columns = static_cast<lapack_int>(state.cols());
    Eigen::VectorXd tau(columns);
    lapack_int info = LAPACKE_dgeqrf(
        LAPACK_COL_MAJOR, rows, columns, state.data(), rows, tau.data()
    );
    if (info != 0) {
        throw std::runtime_error("LAPACKE_dgeqrf failed");
    }
    double log_volume = 0.0;
    for (int index = 0; index < columns; ++index) {
        const double diagonal = state(index, index);
        if (diagonal == 0.0 || !std::isfinite(diagonal)) {
            throw std::runtime_error("singular QR diagonal");
        }
        log_volume += std::log(std::abs(diagonal));
    }
    info = LAPACKE_dorgqr(
        LAPACK_COL_MAJOR, rows, columns, columns, state.data(), rows, tau.data()
    );
    if (info != 0) {
        throw std::runtime_error("LAPACKE_dorgqr failed");
    }
    if (count % 100 == 0) {
        const Matrix gram = state.transpose() * state;
        const double error = (
            gram - Matrix::Identity(columns, columns)
        ).cwiseAbs().maxCoeff();
        maximum_orthogonality = std::max(maximum_orthogonality, error);
    }
    return log_volume;
}

int main(int argc, char **argv) {
    try {
        const Arguments arguments = parse_arguments(argc, argv);
        const double dual = std::atanh(std::exp(-2.0 * arguments.coupling));
        const double normalization = (
            -0.5 * static_cast<double>(arguments.size)
            * std::log(0.5 * std::sinh(2.0 * dual))
        );
        Matrix state = free_state(arguments.size);
        std::mt19937_64 generator(arguments.seed);
        std::bernoulli_distribution negative(arguments.p);
        std::vector<double> vertical(static_cast<std::size_t>(arguments.size));
        std::vector<double> horizontal(static_cast<std::size_t>(arguments.size));
        std::vector<double> blocks;
        blocks.reserve(
            static_cast<std::size_t>(arguments.measurement / arguments.output_block)
        );
        double maximum_orthogonality = 0.0;
        double block_sum = 0.0;
        std::uint64_t rows_in_block = 0;
        std::uint64_t qr_count = 0;
        const std::uint64_t total = arguments.burn_in + arguments.measurement;
        const auto started = std::chrono::steady_clock::now();

        for (std::uint64_t row = 0; row < total; ++row) {
            for (int index = 0; index < arguments.size; ++index) {
                vertical[static_cast<std::size_t>(index)] = negative(generator) ? -1.0 : 1.0;
                horizontal[static_cast<std::size_t>(index)] = negative(generator) ? -1.0 : 1.0;
            }
            apply_vertical(state, vertical, arguments.coupling, arguments.parity);
            apply_horizontal(state, horizontal, arguments.coupling);
            if ((row + 1) % static_cast<std::uint64_t>(arguments.qr_interval) != 0) {
                continue;
            }
            ++qr_count;
            const double log_volume = stabilize(
                state, maximum_orthogonality, qr_count
            );
            if (row + 1 <= arguments.burn_in) {
                continue;
            }
            block_sum += (
                0.5 * log_volume
                + static_cast<double>(arguments.qr_interval) * normalization
            );
            rows_in_block += static_cast<std::uint64_t>(arguments.qr_interval);
            if (rows_in_block == arguments.output_block) {
                blocks.push_back(
                    block_sum
                    / static_cast<double>(arguments.output_block)
                    / static_cast<double>(arguments.size)
                );
                block_sum = 0.0;
                rows_in_block = 0;
            }
        }
        const auto finished = std::chrono::steady_clock::now();
        const double seconds = std::chrono::duration<double>(
            finished - started
        ).count();
        if (blocks.size() != arguments.measurement / arguments.output_block) {
            throw std::runtime_error("block count mismatch");
        }
        std::ofstream output(arguments.output, std::ios::binary);
        output.write(
            reinterpret_cast<const char *>(blocks.data()),
            static_cast<std::streamsize>(blocks.size() * sizeof(double))
        );
        if (!output) {
            throw std::runtime_error("failed to write block output");
        }
        double mean = 0.0;
        for (double value : blocks) {
            mean += value;
        }
        mean /= static_cast<double>(blocks.size());
        std::cout
            << std::setprecision(17)
            << "blocks=" << blocks.size() << "\n"
            << "mean_phi=" << mean << "\n"
            << "maximum_orthogonality_error=" << maximum_orthogonality << "\n"
            << "rows_per_second=" << static_cast<double>(total) / seconds << "\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
