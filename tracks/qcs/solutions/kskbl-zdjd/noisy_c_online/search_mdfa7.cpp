#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <random>
#include <string>
#include <vector>

namespace {

constexpr int kInputs = 5;
constexpr int kGates = 7;
constexpr int kPopulation = 6000;
constexpr int kElite = 300;
constexpr uint32_t kMask = 0xffffffffu;

struct Gate {
    uint8_t op;
    uint8_t left;
    uint8_t right;
    bool invert_left;
    bool invert_right;
};

struct Genome {
    std::array<Gate, kGates> gates;
    int score = std::numeric_limits<int>::max();
    std::array<int, 3> output_wire{};
    std::array<bool, 3> output_inverted{};
};

uint32_t apply_op(uint8_t op, uint32_t left, uint32_t right) {
    if (op == 0) {
        return left & right;
    }
    if (op == 1) {
        return left | right;
    }
    return left ^ right;
}

std::array<uint32_t, kInputs> primary_truth_tables() {
    std::array<uint32_t, kInputs> tables{};
    for (int assignment = 0; assignment < 32; ++assignment) {
        for (int bit = 0; bit < kInputs; ++bit) {
            if ((assignment >> bit) & 1) {
                tables[bit] |= uint32_t{1} << assignment;
            }
        }
    }
    return tables;
}

std::array<uint32_t, 3> target_truth_tables(
    const std::array<uint32_t, kInputs>& input
) {
    const uint32_t single = input[0];
    const uint32_t first_base = input[1];
    const uint32_t first_xor = input[2];
    const uint32_t second_base = input[3];
    const uint32_t second_xor = input[4];
    const uint32_t first_base_xor_single = first_base ^ single;
    const uint32_t disjunction = first_xor | first_base_xor_single;
    const uint32_t first_xor_single = first_xor ^ single;
    const uint32_t carry_base = disjunction ^ first_xor_single;
    const uint32_t second_base_xor = second_base ^ first_xor_single;
    const uint32_t total = first_xor_single ^ second_xor;
    const uint32_t carry_difference =
        second_base_xor & (second_xor ^ kMask);
    const uint32_t carry_xor = disjunction ^ carry_difference;
    return {total, carry_base, carry_xor};
}

int mismatch(uint32_t candidate, uint32_t target) {
    return std::popcount(candidate ^ target);
}

void evaluate(
    Genome& genome,
    const std::array<uint32_t, kInputs>& inputs,
    const std::array<uint32_t, 3>& targets
) {
    std::array<uint32_t, kInputs + kGates> wires{};
    std::copy(inputs.begin(), inputs.end(), wires.begin());
    for (int index = 0; index < kGates; ++index) {
        const Gate& gate = genome.gates[index];
        uint32_t left = wires[gate.left];
        uint32_t right = wires[gate.right];
        if (gate.invert_left) {
            left ^= kMask;
        }
        if (gate.invert_right) {
            right ^= kMask;
        }
        wires[kInputs + index] = apply_op(gate.op, left, right);
    }

    genome.score = 0;
    for (int output = 0; output < 3; ++output) {
        int best = 33;
        int best_wire = 0;
        bool best_inverted = false;
        for (int wire = 0; wire < kInputs + kGates; ++wire) {
            const int direct = mismatch(wires[wire], targets[output]);
            const int inverted = mismatch(
                wires[wire] ^ kMask,
                targets[output]
            );
            if (direct < best) {
                best = direct;
                best_wire = wire;
                best_inverted = false;
            }
            if (inverted < best) {
                best = inverted;
                best_wire = wire;
                best_inverted = true;
            }
        }
        genome.score += best;
        genome.output_wire[output] = best_wire;
        genome.output_inverted[output] = best_inverted;
    }
}

Gate random_gate(int gate_index, std::mt19937_64& generator) {
    const int wire_count = kInputs + gate_index;
    std::uniform_int_distribution<int> op_distribution(0, 2);
    std::uniform_int_distribution<int> wire_distribution(0, wire_count - 1);
    std::bernoulli_distribution bit_distribution(0.5);
    Gate gate{
        static_cast<uint8_t>(op_distribution(generator)),
        static_cast<uint8_t>(wire_distribution(generator)),
        static_cast<uint8_t>(wire_distribution(generator)),
        bit_distribution(generator),
        bit_distribution(generator),
    };
    if (gate.right < gate.left) {
        std::swap(gate.left, gate.right);
        std::swap(gate.invert_left, gate.invert_right);
    }
    return gate;
}

Genome random_genome(std::mt19937_64& generator) {
    Genome genome;
    for (int index = 0; index < kGates; ++index) {
        genome.gates[index] = random_gate(index, generator);
    }
    return genome;
}

void mutate(Genome& genome, std::mt19937_64& generator);

std::array<Gate, 8> known_eight_gate_mdfa() {
    return {
        Gate{2, 0, 1, false, false},
        Gate{1, 2, 5, false, false},
        Gate{2, 0, 2, false, false},
        Gate{2, 6, 7, false, false},
        Gate{2, 3, 7, false, false},
        Gate{2, 4, 7, false, false},
        Gate{0, 4, 9, true, false},
        Gate{2, 6, 11, false, false},
    };
}

Genome seeded_from_eight_gate(
    int skipped_gate,
    std::mt19937_64& generator
) {
    const auto known = known_eight_gate_mdfa();
    std::array<int, kInputs + 8> remap{};
    remap.fill(-1);
    for (int input = 0; input < kInputs; ++input) {
        remap[input] = input;
    }
    Genome genome;
    int new_gate = 0;
    for (int old_gate = 0; old_gate < 8; ++old_gate) {
        if (old_gate == skipped_gate) {
            continue;
        }
        Gate gate = known[old_gate];
        const int wire_count = kInputs + new_gate;
        std::uniform_int_distribution<int> fallback(0, wire_count - 1);
        const int remapped_left = remap[gate.left];
        const int remapped_right = remap[gate.right];
        gate.left = static_cast<uint8_t>(
            remapped_left >= 0 ? remapped_left : fallback(generator)
        );
        gate.right = static_cast<uint8_t>(
            remapped_right >= 0 ? remapped_right : fallback(generator)
        );
        if (gate.right < gate.left) {
            std::swap(gate.left, gate.right);
            std::swap(gate.invert_left, gate.invert_right);
        }
        genome.gates[new_gate] = gate;
        remap[kInputs + old_gate] = kInputs + new_gate;
        ++new_gate;
    }
    mutate(genome, generator);
    return genome;
}

void mutate(Genome& genome, std::mt19937_64& generator) {
    std::uniform_int_distribution<int> mutation_count_distribution(1, 4);
    std::uniform_int_distribution<int> gate_distribution(0, kGates - 1);
    std::uniform_int_distribution<int> field_distribution(0, 4);
    std::uniform_int_distribution<int> op_distribution(0, 2);
    std::bernoulli_distribution bit_distribution(0.5);
    const int mutations = mutation_count_distribution(generator);
    for (int mutation = 0; mutation < mutations; ++mutation) {
        const int index = gate_distribution(generator);
        Gate& gate = genome.gates[index];
        const int wire_count = kInputs + index;
        std::uniform_int_distribution<int> wire_distribution(
            0,
            wire_count - 1
        );
        switch (field_distribution(generator)) {
            case 0:
                gate.op = static_cast<uint8_t>(op_distribution(generator));
                break;
            case 1:
                gate.left = static_cast<uint8_t>(
                    wire_distribution(generator)
                );
                break;
            case 2:
                gate.right = static_cast<uint8_t>(
                    wire_distribution(generator)
                );
                break;
            case 3:
                gate.invert_left = bit_distribution(generator);
                break;
            default:
                gate.invert_right = bit_distribution(generator);
                break;
        }
        if (gate.right < gate.left) {
            std::swap(gate.left, gate.right);
            std::swap(gate.invert_left, gate.invert_right);
        }
    }
}

Genome crossover(
    const Genome& first,
    const Genome& second,
    std::mt19937_64& generator
) {
    std::bernoulli_distribution choose_first(0.5);
    Genome child;
    for (int index = 0; index < kGates; ++index) {
        child.gates[index] = choose_first(generator)
            ? first.gates[index]
            : second.gates[index];
    }
    mutate(child, generator);
    return child;
}

const Genome& tournament(
    const std::vector<Genome>& population,
    std::mt19937_64& generator
) {
    std::uniform_int_distribution<int> distribution(
        0,
        static_cast<int>(population.size()) - 1
    );
    const Genome* best = nullptr;
    for (int draw = 0; draw < 6; ++draw) {
        const Genome& candidate = population[distribution(generator)];
        if (best == nullptr || candidate.score < best->score) {
            best = &candidate;
        }
    }
    return *best;
}

std::string wire_name(int wire) {
    if (wire < kInputs) {
        return "i" + std::to_string(wire);
    }
    return "g" + std::to_string(wire - kInputs);
}

std::string token_name(int wire, bool inverted) {
    return std::string(inverted ? "~" : "") + wire_name(wire);
}

std::string op_name(uint8_t op) {
    if (op == 0) {
        return "AND";
    }
    if (op == 1) {
        return "OR";
    }
    return "XOR";
}

void write_result(
    const Genome& genome,
    uint64_t seed,
    uint64_t evaluations,
    const std::string& output_path,
    bool exact
) {
    std::ofstream output(output_path);
    output << "{\n";
    output << "  \"kind\": \"seven-gate-mdfa-evolution-search\",\n";
    output << "  \"seed\": " << seed << ",\n";
    output << "  \"evaluations\": " << evaluations << ",\n";
    output << "  \"input_order\": [\"single\", \"first_base\", "
              "\"first_xor\", \"second_base\", \"second_xor\"],\n";
    output << "  \"gates\": [\n";
    for (int index = 0; index < kGates; ++index) {
        const Gate& gate = genome.gates[index];
        output << "    {\"op\": \"" << op_name(gate.op)
               << "\", \"a\": \""
               << token_name(gate.left, gate.invert_left)
               << "\", \"b\": \""
               << token_name(gate.right, gate.invert_right)
               << "\", \"out\": \"g" << index << "\"}";
        output << (index + 1 == kGates ? "\n" : ",\n");
    }
    output << "  ],\n";
    output << "  \"outputs\": [\n";
    const std::array<std::string, 3> names{
        "total",
        "carry_base",
        "carry_xor",
    };
    for (int index = 0; index < 3; ++index) {
        output << "    {\"name\": \"" << names[index]
               << "\", \"token\": \""
               << token_name(
                      genome.output_wire[index],
                      genome.output_inverted[index]
                  )
               << "\"}";
        output << (index == 2 ? "\n" : ",\n");
    }
    output << "  ],\n";
    output << "  \"verification\": {\"all_32_inputs_exact\": "
           << (exact ? "true" : "false")
           << ", \"total_hamming_mismatch\": " << genome.score << "}\n";
    output << "}\n";
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 4) {
        std::cerr << "usage: search_mdfa7 SEED GENERATIONS OUTPUT.json\n";
        return 2;
    }
    const uint64_t seed = std::stoull(argv[1]);
    const int generations = std::stoi(argv[2]);
    const std::string output_path = argv[3];
    std::mt19937_64 generator(seed);
    const auto inputs = primary_truth_tables();
    const auto targets = target_truth_tables(inputs);
    std::vector<Genome> population;
    population.reserve(kPopulation);
    uint64_t evaluations = 0;
    for (int index = 0; index < kPopulation; ++index) {
        if (index < kPopulation / 2) {
            population.push_back(
                seeded_from_eight_gate(index % 8, generator)
            );
        } else {
            population.push_back(random_genome(generator));
        }
        evaluate(population.back(), inputs, targets);
        ++evaluations;
    }

    for (int generation = 0; generation < generations; ++generation) {
        std::sort(
            population.begin(),
            population.end(),
            [](const Genome& left, const Genome& right) {
                return left.score < right.score;
            }
        );
        if (generation % 500 == 0) {
            std::cout << "generation=" << generation
                      << " best_score=" << population.front().score
                      << " evaluations=" << evaluations << "\n";
        }
        if (population.front().score == 0) {
            write_result(
                population.front(),
                seed,
                evaluations,
                output_path,
                true
            );
            std::cout << "exact seven-gate MDFA found: "
                      << output_path << "\n";
            return 0;
        }

        std::vector<Genome> next;
        next.reserve(kPopulation);
        for (int index = 0; index < kElite; ++index) {
            next.push_back(population[index]);
        }
        while (static_cast<int>(next.size()) < kPopulation) {
            Genome child;
            if (static_cast<int>(next.size()) > 9 * kPopulation / 10) {
                child = random_genome(generator);
            } else {
                const Genome& first = tournament(population, generator);
                const Genome& second = tournament(population, generator);
                child = crossover(first, second, generator);
            }
            evaluate(child, inputs, targets);
            ++evaluations;
            next.push_back(child);
        }
        population.swap(next);
    }

    std::sort(
        population.begin(),
        population.end(),
        [](const Genome& left, const Genome& right) {
            return left.score < right.score;
        }
    );
    std::cout << "no exact circuit; best_score="
              << population.front().score
              << " evaluations=" << evaluations << "\n";
    write_result(
        population.front(),
        seed,
        evaluations,
        output_path,
        false
    );
    return 1;
}
