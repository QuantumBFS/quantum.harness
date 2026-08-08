#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <future>
#include <iostream>
#include <memory>
#include <queue>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

namespace fs = std::filesystem;

struct Record {
    std::uint64_t key;
    std::uint64_t value;
};

class RunReader {
public:
    explicit RunReader(const fs::path& path)
        : input_(path, std::ios::binary), buffer_(1 << 16) {
        if (!input_) {
            throw std::runtime_error("cannot open run: " + path.string());
        }
    }

    bool next(Record& record) {
        if (position_ == size_) {
            input_.read(
                reinterpret_cast<char*>(buffer_.data()),
                static_cast<std::streamsize>(
                    buffer_.size() * sizeof(Record)
                )
            );
            const auto bytes = input_.gcount();
            if (bytes == 0) {
                return false;
            }
            if (bytes % static_cast<std::streamsize>(sizeof(Record)) != 0) {
                throw std::runtime_error("truncated sorted run");
            }
            size_ = static_cast<std::size_t>(bytes) / sizeof(Record);
            position_ = 0;
        }
        record = buffer_[position_++];
        return true;
    }

private:
    std::ifstream input_;
    std::vector<Record> buffer_;
    std::size_t position_ = 0;
    std::size_t size_ = 0;
};

struct Node {
    std::uint64_t key;
    std::uint64_t value;
    std::size_t run;
};

struct GreaterNode {
    bool operator()(const Node& left, const Node& right) const {
        if (left.key != right.key) {
            return left.key > right.key;
        }
        return left.run > right.run;
    }
};

template <typename Emit>
std::uint64_t merge_records(
    const std::vector<fs::path>& paths,
    Emit emit
) {
    std::vector<std::unique_ptr<RunReader>> readers;
    readers.reserve(paths.size());
    for (const auto& path : paths) {
        readers.push_back(std::make_unique<RunReader>(path));
    }
    std::priority_queue<Node, std::vector<Node>, GreaterNode> queue;
    for (std::size_t run = 0; run < readers.size(); ++run) {
        Record record{};
        if (readers[run]->next(record)) {
            queue.push(Node{record.key, record.value, run});
        }
    }

    std::uint64_t output_count = 0;
    while (!queue.empty()) {
        const auto key = queue.top().key;
        std::uint64_t value = 0;
        do {
            const auto node = queue.top();
            queue.pop();
            value += node.value;
            Record next_record{};
            if (readers[node.run]->next(next_record)) {
                queue.push(
                    Node{next_record.key, next_record.value, node.run}
                );
            }
        } while (!queue.empty() && queue.top().key == key);
        if (value != 0) {
            emit(Record{key, value});
            ++output_count;
        }
    }
    return output_count;
}

void write_count_marker(const fs::path& marker, std::uint64_t count) {
    const auto partial = marker.string() + ".partial";
    {
        std::ofstream output(partial);
        if (!output) {
            throw std::runtime_error(
                "cannot write completion marker: " + marker.string()
            );
        }
        output << count << '\n';
    }
    fs::rename(partial, marker);
}

bool read_count_marker(const fs::path& marker, std::uint64_t& count) {
    std::ifstream input(marker);
    return static_cast<bool>(input >> count);
}

std::uint64_t merge_interleaved(
    const std::vector<fs::path>& inputs,
    const fs::path& output
) {
    const fs::path marker = output.string() + ".complete";
    std::uint64_t completed_count = 0;
    if (
        fs::exists(output)
        && read_count_marker(marker, completed_count)
    ) {
        return completed_count;
    }

    const fs::path partial = output.string() + ".partial";
    fs::remove(partial);
    std::ofstream stream(partial, std::ios::binary);
    if (!stream) {
        throw std::runtime_error(
            "cannot open intermediate output: " + partial.string()
        );
    }
    constexpr std::size_t buffer_cells = 1 << 20;
    std::vector<Record> buffer;
    buffer.reserve(buffer_cells);
    const auto count = merge_records(inputs, [&](const Record& record) {
        buffer.push_back(record);
        if (buffer.size() == buffer_cells) {
            stream.write(
                reinterpret_cast<const char*>(buffer.data()),
                static_cast<std::streamsize>(
                    buffer.size() * sizeof(Record)
                )
            );
            buffer.clear();
        }
    });
    if (!buffer.empty()) {
        stream.write(
            reinterpret_cast<const char*>(buffer.data()),
            static_cast<std::streamsize>(buffer.size() * sizeof(Record))
        );
    }
    stream.close();
    if (!stream) {
        throw std::runtime_error(
            "failed writing intermediate output: " + partial.string()
        );
    }
    fs::remove(output);
    fs::rename(partial, output);
    write_count_marker(marker, count);
    return count;
}

std::uint64_t merge_split(
    const std::vector<fs::path>& inputs,
    const fs::path& key_output,
    const fs::path& value_output,
    const fs::path& marker
) {
    std::uint64_t completed_count = 0;
    if (
        fs::exists(key_output)
        && fs::exists(value_output)
        && read_count_marker(marker, completed_count)
    ) {
        return completed_count;
    }

    const fs::path partial_keys = key_output.string() + ".partial";
    const fs::path partial_values = value_output.string() + ".partial";
    fs::remove(partial_keys);
    fs::remove(partial_values);
    std::ofstream keys(partial_keys, std::ios::binary);
    std::ofstream values(partial_values, std::ios::binary);
    if (!keys || !values) {
        throw std::runtime_error("cannot open final merged output");
    }
    constexpr std::size_t buffer_cells = 1 << 20;
    std::vector<std::uint64_t> key_buffer;
    std::vector<std::uint64_t> value_buffer;
    key_buffer.reserve(buffer_cells);
    value_buffer.reserve(buffer_cells);

    auto flush = [&]() {
        keys.write(
            reinterpret_cast<const char*>(key_buffer.data()),
            static_cast<std::streamsize>(
                key_buffer.size() * sizeof(std::uint64_t)
            )
        );
        values.write(
            reinterpret_cast<const char*>(value_buffer.data()),
            static_cast<std::streamsize>(
                value_buffer.size() * sizeof(std::uint64_t)
            )
        );
        key_buffer.clear();
        value_buffer.clear();
    };
    const auto count = merge_records(inputs, [&](const Record& record) {
        key_buffer.push_back(record.key);
        value_buffer.push_back(record.value);
        if (key_buffer.size() == buffer_cells) {
            flush();
        }
    });
    if (!key_buffer.empty()) {
        flush();
    }
    keys.close();
    values.close();
    if (!keys || !values) {
        throw std::runtime_error("failed writing final merged output");
    }
    fs::remove(key_output);
    fs::remove(value_output);
    fs::rename(partial_keys, key_output);
    fs::rename(partial_values, value_output);
    write_count_marker(marker, count);
    return count;
}

std::size_t parse_positive(const std::string& text, const char* option) {
    const auto value = std::stoull(text);
    if (value == 0) {
        throw std::runtime_error(std::string(option) + " must be positive");
    }
    return static_cast<std::size_t>(value);
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc < 4) {
            throw std::runtime_error(
                "usage: merge_sorted_runs OUTPUT_KEYS OUTPUT_VALUES MANIFEST "
                "[--fan-in N] [--threads N] [--workspace DIRECTORY]"
            );
        }
        const fs::path key_output = argv[1];
        const fs::path value_output = argv[2];
        const fs::path manifest_path = argv[3];
        std::size_t fan_in = 64;
        const auto hardware_threads = std::max(
            1u, std::thread::hardware_concurrency()
        );
        std::size_t threads = std::min<std::size_t>(8, hardware_threads);
        fs::path workspace = key_output.parent_path() / "merge_stages";
        for (int argument = 4; argument < argc; ++argument) {
            const std::string option = argv[argument];
            if (argument + 1 >= argc) {
                throw std::runtime_error("missing value for " + option);
            }
            const std::string value = argv[++argument];
            if (option == "--fan-in") {
                fan_in = parse_positive(value, "--fan-in");
            } else if (option == "--threads") {
                threads = parse_positive(value, "--threads");
            } else if (option == "--workspace") {
                workspace = value;
            } else {
                throw std::runtime_error("unknown option: " + option);
            }
        }
        if (fan_in < 2) {
            throw std::runtime_error("--fan-in must be at least 2");
        }
        fs::create_directories(workspace);

        std::ifstream manifest(manifest_path);
        if (!manifest) {
            throw std::runtime_error("cannot open run manifest");
        }
        std::vector<fs::path> current;
        std::string path;
        while (std::getline(manifest, path)) {
            if (!path.empty()) {
                current.emplace_back(path);
            }
        }

        std::size_t pass = 0;
        while (current.size() > fan_in) {
            const auto group_count =
                (current.size() + fan_in - 1) / fan_in;
            std::vector<fs::path> next(group_count);
            for (std::size_t group = 0; group < group_count; ++group) {
                next[group] = workspace / (
                    "pass_" + std::to_string(pass)
                    + "_group_" + std::to_string(group) + ".bin"
                );
            }

            for (
                std::size_t wave = 0;
                wave < group_count;
                wave += threads
            ) {
                const auto wave_end = std::min(
                    group_count, wave + threads
                );
                std::vector<std::future<std::uint64_t>> futures;
                futures.reserve(wave_end - wave);
                for (std::size_t group = wave; group < wave_end; ++group) {
                    const auto begin = group * fan_in;
                    const auto end = std::min(
                        current.size(), begin + fan_in
                    );
                    std::vector<fs::path> inputs(
                        current.begin() + begin, current.begin() + end
                    );
                    futures.push_back(std::async(
                        std::launch::async,
                        [inputs = std::move(inputs), output = next[group]]() {
                            return merge_interleaved(inputs, output);
                        }
                    ));
                }
                for (auto& future : futures) {
                    future.get();
                }
            }
            current = std::move(next);
            ++pass;
        }

        const auto marker = workspace / "final.complete";
        const auto output_count = merge_split(
            current, key_output, value_output, marker
        );
        std::cout << output_count << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
