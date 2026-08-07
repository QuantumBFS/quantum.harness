#include "archive_reader.hpp"
#include "archive_replay.hpp"
#include "batch_replay.hpp"
#include "enumerator.hpp"
#include "fock_oracle.hpp"
#include "replay.hpp"
#include "trial_io.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <numeric>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

using Options = std::map<std::string, std::string>;

struct NamedTrial {
    std::string name;
    audit::TrialCode code;
    audit::TrialState state;
};

struct NamedResult {
    std::string file;
    std::string trial;
    std::string proposal;
    std::string order;
    audit::EnumerationResult result;
    double direct_projection = 0.0;
    double sum_residual = 0.0;
};

struct ArchiveIndexEntry {
    std::filesystem::path path;
    std::uint8_t ensemble_code = 0;
    std::uint32_t chain = 0;
};

struct RequestedSample {
    std::uint8_t ensemble_code = 0;
    std::uint32_t chain = 0;
};

struct LoadedArchiveRecord {
    audit::ArchiveHeader header;
    audit::ArchiveRecordView record;
};

Options parse_options(int argc, char** argv, int first) {
    Options options;
    for (int index = first; index < argc; ++index) {
        const std::string key = argv[index];
        if (key.rfind("--", 0) != 0) {
            throw std::invalid_argument("expected option, got: " + key);
        }
        if (index + 1 >= argc ||
            std::string(argv[index + 1]).rfind("--", 0) == 0) {
            options[key.substr(2)] = "true";
        } else {
            options[key.substr(2)] = argv[++index];
        }
    }
    return options;
}

std::string value(const Options& options, const std::string& key,
                  const std::string& fallback) {
    const auto found = options.find(key);
    return found == options.end() ? fallback : found->second;
}

std::size_t size_value(const Options& options, const std::string& key,
                       std::size_t fallback) {
    return static_cast<std::size_t>(
        std::stoull(value(options, key, std::to_string(fallback))));
}

double real_value(const Options& options, const std::string& key,
                  double fallback) {
    const auto found = options.find(key);
    return found == options.end() ? fallback : std::stod(found->second);
}

std::uint64_t uint64_value(const Options& options,
                           const std::string& key) {
    const auto found = options.find(key);
    if (found == options.end()) {
        throw std::invalid_argument("missing required option --" + key);
    }
    return std::stoull(found->second, nullptr, 0);
}

std::string required_value(const Options& options,
                           const std::string& key) {
    const auto found = options.find(key);
    if (found == options.end() || found->second.empty()) {
        throw std::invalid_argument("missing required option --" + key);
    }
    return found->second;
}

std::vector<std::string> split(const std::string& text) {
    std::vector<std::string> result;
    std::stringstream stream(text);
    std::string item;
    while (std::getline(stream, item, ',')) {
        if (!item.empty()) {
            result.push_back(item);
        }
    }
    if (result.empty()) {
        throw std::invalid_argument("empty comma-separated option");
    }
    return result;
}

std::string read_text_file(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open text contract: " +
                                 path.string());
    }
    return std::string(
        std::istreambuf_iterator<char>(input),
        std::istreambuf_iterator<char>()
    );
}

double json_number(const std::string& text, const std::string& key) {
    const std::regex pattern(
        "\"" + key +
        "\"\\s*:\\s*([-+]?(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)"
        "(?:[eE][-+]?[0-9]+)?)"
    );
    std::smatch match;
    if (!std::regex_search(text, match, pattern)) {
        throw std::runtime_error("missing JSON number: " + key);
    }
    return std::stod(match[1].str());
}

std::string json_string(const std::string& text,
                        const std::string& key) {
    const std::regex pattern(
        "\"" + key + "\"\\s*:\\s*\"([^\"]*)\""
    );
    std::smatch match;
    if (!std::regex_search(text, match, pattern)) {
        throw std::runtime_error("missing JSON string: " + key);
    }
    return match[1].str();
}

std::vector<ArchiveIndexEntry> read_archive_index(
    const std::filesystem::path& path
) {
    const std::string text = read_text_file(path);
    std::vector<ArchiveIndexEntry> result;
    std::set<std::pair<unsigned, unsigned>> seen;
    const std::regex object_pattern("\\{[^\\{\\}]*\"path\"[^\\{\\}]*\\}");
    for (auto iterator = std::sregex_iterator(
             text.begin(), text.end(), object_pattern);
         iterator != std::sregex_iterator(); ++iterator) {
        const std::string object = iterator->str();
        const std::string archive_path = json_string(object, "path");
        const std::string ensemble = json_string(object, "ensemble");
        const auto chain = static_cast<std::uint32_t>(
            json_number(object, "chain")
        );
        const std::uint8_t code =
            ensemble == "II" ? 1 : ensemble == "TI" ? 2 : 0;
        if (code == 0 || chain >= 2048 ||
            !seen.emplace(code, chain).second) {
            throw std::runtime_error(
                "invalid or duplicate archive index entry"
            );
        }
        std::filesystem::path resolved(archive_path);
        if (resolved.is_relative()) {
            resolved = path.parent_path() / resolved;
        }
        result.push_back({std::filesystem::absolute(resolved), code, chain});
    }
    if (result.empty()) {
        throw std::runtime_error("archive index has no flat entries");
    }
    return result;
}

std::map<std::uint64_t, RequestedSample> read_sample_manifest(
    const std::filesystem::path& path
) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open sample manifest: " +
                                 path.string());
    }
    std::string line;
    if (!std::getline(input, line) ||
        line != "sample_id,ensemble,chain") {
        throw std::runtime_error("unexpected sample manifest header");
    }
    std::map<std::uint64_t, RequestedSample> result;
    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }
        std::stringstream row(line);
        std::string id_text;
        std::string ensemble;
        std::string chain_text;
        std::string extra;
        if (!std::getline(row, id_text, ',') ||
            !std::getline(row, ensemble, ',') ||
            !std::getline(row, chain_text, ',') ||
            std::getline(row, extra, ',')) {
            throw std::runtime_error("malformed sample manifest row");
        }
        const auto id = std::stoull(id_text);
        const auto chain =
            static_cast<std::uint32_t>(std::stoul(chain_text));
        const std::uint8_t code =
            ensemble == "II" ? 1 : ensemble == "TI" ? 2 : 0;
        if (code == 0 || chain >= 2048 ||
            !result.emplace(id, RequestedSample{code, chain}).second) {
            throw std::runtime_error(
                "invalid or duplicate sample manifest row"
            );
        }
    }
    if (result.empty()) {
        throw std::runtime_error("sample manifest contains no paths");
    }
    return result;
}

audit::HubbardModel make_model(const Options& options) {
    const std::size_t lx = size_value(options, "lx", 2);
    const std::size_t ly = size_value(options, "ly", 2);
    const std::size_t sites = lx * ly;
    const std::size_t n_up = size_value(options, "n-up", sites / 2);
    const std::size_t n_down = size_value(options, "n-down", sites / 2);
    return audit::HubbardModel::square_periodic(
        lx, ly, real_value(options, "t", 1.0),
        real_value(options, "u", 8.0), real_value(options, "dt", 0.1),
        n_up, n_down);
}

struct SiteMap {
    std::vector<std::size_t> cpp_by_alf;
};

SiteMap read_site_map(const std::filesystem::path& path,
                      const audit::HubbardModel& model) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open site map: " + path.string());
    }
    SiteMap result;
    result.cpp_by_alf.assign(model.sites(), model.sites());
    std::vector<bool> cpp_seen(model.sites(), false);
    std::size_t alf_one_based = 0;
    std::size_t cpp = 0;
    std::size_t x = 0;
    std::size_t y = 0;
    std::size_t rows = 0;
    while (input >> alf_one_based >> cpp >> x >> y) {
        if (alf_one_based == 0 || alf_one_based > model.sites() ||
            cpp >= model.sites() || x >= model.lx() || y >= model.ly() ||
            cpp != y * model.lx() + x ||
            result.cpp_by_alf.at(alf_one_based - 1) != model.sites() ||
            cpp_seen.at(cpp)) {
            throw std::runtime_error("site map is not a valid ALF-to-C++ bijection");
        }
        result.cpp_by_alf.at(alf_one_based - 1) = cpp;
        cpp_seen.at(cpp) = true;
        ++rows;
    }
    if (!input.eof() || rows != model.sites() ||
        std::find(cpp_seen.begin(), cpp_seen.end(), false) !=
            cpp_seen.end()) {
        throw std::runtime_error("site map is incomplete or malformed");
    }
    return result;
}

audit::Matrix alf_to_cpp(const audit::Matrix& source,
                         const SiteMap& map) {
    if (source.rows() != map.cpp_by_alf.size()) {
        throw std::invalid_argument("site-map/orbital size mismatch");
    }
    audit::Matrix result(source.rows(), source.cols());
    for (std::size_t alf = 0; alf < source.rows(); ++alf) {
        const std::size_t cpp = map.cpp_by_alf.at(alf);
        for (std::size_t col = 0; col < source.cols(); ++col) {
            result(cpp, col) = source(alf, col);
        }
    }
    return result;
}

audit::Matrix cpp_to_alf(const audit::Matrix& source,
                         const SiteMap& map) {
    if (source.rows() != map.cpp_by_alf.size()) {
        throw std::invalid_argument("site-map/orbital size mismatch");
    }
    audit::Matrix result(source.rows(), source.cols());
    for (std::size_t alf = 0; alf < source.rows(); ++alf) {
        const std::size_t cpp = map.cpp_by_alf.at(alf);
        for (std::size_t col = 0; col < source.cols(); ++col) {
            result(alf, col) = source(cpp, col);
        }
    }
    return result;
}

double staggered_magnetization(const audit::TrialState& trial,
                               const audit::HubbardModel& model) {
    double result = 0.0;
    for (std::size_t site = 0; site < model.sites(); ++site) {
        result += model.sublattice(site) *
                  (trial.up_density().at(site) -
                   trial.down_density().at(site));
    }
    return result / static_cast<double>(model.sites());
}

int export_uhf_command(const Options& options) {
    const auto model = make_model(options);
    const auto initial_up_path =
        std::filesystem::path(required_value(options, "initial-up"));
    const auto initial_down_path =
        std::filesystem::path(required_value(options, "initial-down"));
    const auto site_map_path =
        std::filesystem::path(required_value(options, "site-map"));
    const auto output_dir =
        std::filesystem::path(required_value(options, "output-dir"));

    const auto initial_up_alf = audit::read_real_orbitals(
        initial_up_path.string(), model.sites(), model.n_up());
    const auto initial_down_alf = audit::read_real_orbitals(
        initial_down_path.string(), model.sites(), model.n_down());
    const SiteMap site_map = read_site_map(site_map_path, model);
    const auto initial_up = alf_to_cpp(initial_up_alf, site_map);
    const auto initial_down = alf_to_cpp(initial_down_alf, site_map);

    const double initial_up_orth =
        audit::orthonormality_residual(initial_up);
    const double initial_down_orth =
        audit::orthonormality_residual(initial_down);
    if (initial_up_orth >= 1.0e-11 ||
        initial_down_orth >= 1.0e-11) {
        throw std::runtime_error("initial orbitals are not orthonormal");
    }

    const double uhf_u = real_value(options, "uhf-u", model.u());
    const double mixing = real_value(options, "mixing", 0.2);
    const double tolerance = real_value(options, "tolerance", 1.0e-12);
    const auto uhf = audit::TrialState::solve_uhf(
        model, uhf_u, 0.5, mixing, tolerance, 10000);
    audit::Matrix trial_up = uhf.up_orbitals();
    audit::Matrix trial_down = uhf.down_orbitals();
    const double overlap_up =
        audit::orient_overlap_positive(trial_up, initial_up);
    const double overlap_down =
        audit::orient_overlap_positive(trial_down, initial_down);

    const double trial_up_orth =
        audit::orthonormality_residual(trial_up);
    const double trial_down_orth =
        audit::orthonormality_residual(trial_down);
    const double initial_ph = audit::particle_hole_projector_residual(
        initial_up, initial_down, model);
    const double trial_ph = audit::particle_hole_projector_residual(
        trial_up, trial_down, model);
    const double staggered = staggered_magnetization(uhf, model);
    if (trial_up_orth >= 1.0e-11 ||
        trial_down_orth >= 1.0e-11 || initial_ph >= 1.0e-10 ||
        trial_ph >= 1.0e-10 || !(staggered > 0.0)) {
        throw std::runtime_error("UHF orbital validation failed");
    }

    std::filesystem::create_directories(output_dir);
    audit::write_real_orbitals(
        (output_dir / "trial_T_up.dat").string(),
        cpp_to_alf(trial_up, site_map));
    audit::write_real_orbitals(
        (output_dir / "trial_T_down.dat").string(),
        cpp_to_alf(trial_down, site_map));

    std::ofstream metadata(output_dir / "uhf_metadata.json");
    if (!metadata) {
        throw std::runtime_error("cannot write UHF metadata");
    }
    metadata << std::setprecision(17)
             << "{\n"
             << "  \"format_version\": 1,\n"
             << "  \"uhf_u\": " << uhf_u << ",\n"
             << "  \"mixing\": " << mixing << ",\n"
             << "  \"tolerance\": " << tolerance << ",\n"
             << "  \"scf_converged\": "
             << (uhf.scf_converged() ? "true" : "false") << ",\n"
             << "  \"scf_iterations\": " << uhf.scf_iterations() << ",\n"
             << "  \"scf_residual\": " << uhf.scf_residual() << ",\n"
             << "  \"scf_energy\": " << uhf.scf_energy() << ",\n"
             << "  \"staggered_magnetization\": " << staggered << ",\n"
             << "  \"orthonormality_residuals\": {\n"
             << "    \"I_up\": " << initial_up_orth << ",\n"
             << "    \"I_down\": " << initial_down_orth << ",\n"
             << "    \"T_up\": " << trial_up_orth << ",\n"
             << "    \"T_down\": " << trial_down_orth << "\n"
             << "  },\n"
             << "  \"particle_hole_residuals\": {\n"
             << "    \"I\": " << initial_ph << ",\n"
             << "    \"T\": " << trial_ph << "\n"
             << "  },\n"
             << "  \"spin_overlap_determinants\": {\n"
             << "    \"up\": " << overlap_up << ",\n"
             << "    \"down\": " << overlap_down << "\n"
             << "  }\n"
             << "}\n";
    std::cout << "PASS: exported UHF orbitals to " << output_dir
              << ", overlaps=" << overlap_up << ',' << overlap_down
              << ", SCF iterations=" << uhf.scf_iterations() << '\n';
    return 0;
}

NamedTrial make_trial(const std::string& name,
                      const audit::HubbardModel& model) {
    if (name == "rhf_x") {
        return {name, audit::TrialCode::RhfX,
                audit::TrialState::rhf_x(model)};
    }
    if (name == "rhf_y") {
        return {name, audit::TrialCode::RhfY,
                audit::TrialState::rhf_y(model)};
    }
    if (name == "uhf") {
        return {name, audit::TrialCode::Uhf,
                audit::TrialState::solve_uhf(model, model.u())};
    }
    throw std::invalid_argument("unknown trial: " + name);
}

std::pair<audit::SiteOrderCode, std::vector<std::size_t>> make_order(
    const std::string& name, const audit::HubbardModel& model) {
    if (name == "row") {
        return {audit::SiteOrderCode::RowMajor,
                model.row_major_order()};
    }
    if (name == "reverse") {
        return {audit::SiteOrderCode::Reverse, model.reverse_order()};
    }
    if (name == "sublattice") {
        return {audit::SiteOrderCode::Sublattice,
                model.sublattice_order()};
    }
    throw std::invalid_argument("unknown site order: " + name);
}

std::string trial_name(audit::TrialCode code) {
    switch (code) {
        case audit::TrialCode::RhfX:
            return "rhf_x";
        case audit::TrialCode::RhfY:
            return "rhf_y";
        case audit::TrialCode::Uhf:
            return "uhf";
    }
    throw std::invalid_argument("unknown trial code in path file");
}

audit::ProposalKind proposal_kind(audit::ProposalCode code) {
    if (code == audit::ProposalCode::SiteBySite) {
        return audit::ProposalKind::SiteBySite;
    }
    if (code == audit::ProposalCode::JointSlice) {
        return audit::ProposalKind::JointSlice;
    }
    throw std::invalid_argument("unknown proposal code in path file");
}

std::vector<std::size_t> order_from_code(
    audit::SiteOrderCode code, const audit::HubbardModel& model) {
    switch (code) {
        case audit::SiteOrderCode::RowMajor:
            return model.row_major_order();
        case audit::SiteOrderCode::Reverse:
            return model.reverse_order();
        case audit::SiteOrderCode::Sublattice:
            return model.sublattice_order();
        case audit::SiteOrderCode::NotApplicable:
            return model.row_major_order();
    }
    throw std::invalid_argument("unknown site-order code in path file");
}

void write_metadata(const std::filesystem::path& path,
                    const audit::HubbardModel& model, std::size_t slices,
                    const std::vector<NamedTrial>& trials) {
    std::ofstream stream(path);
    if (!stream) {
        throw std::runtime_error("cannot write metadata: " + path.string());
    }
    stream << std::setprecision(17);
    stream << "{\n"
           << "  \"format\": \"cpmc-path-audit-v1\",\n"
           << "  \"field_order\": \"slice-major, site-major, earliest field is the most-significant config-id bit\",\n"
           << "  \"lx\": " << model.lx() << ",\n"
           << "  \"ly\": " << model.ly() << ",\n"
           << "  \"pbc_x\": true,\n"
           << "  \"pbc_y\": true,\n"
           << "  \"t\": " << model.hopping() << ",\n"
           << "  \"u\": " << model.u() << ",\n"
           << "  \"dt\": " << model.dt() << ",\n"
           << "  \"n_up\": " << model.n_up() << ",\n"
           << "  \"n_down\": " << model.n_down() << ",\n"
           << "  \"slices\": " << slices << ",\n"
           << "  \"gamma\": " << model.gamma() << ",\n"
           << "  \"slice_constant\": " << model.slice_constant() << ",\n"
           << "  \"trials\": [\n";
    for (std::size_t index = 0; index < trials.size(); ++index) {
        const auto& trial = trials.at(index);
        stream << "    {\"name\": \"" << trial.name
               << "\", \"scf_converged\": "
               << (trial.state.scf_converged() ? "true" : "false")
               << ", \"scf_iterations\": "
               << trial.state.scf_iterations() << ", \"scf_residual\": "
               << trial.state.scf_residual() << ", \"scf_energy\": "
               << trial.state.scf_energy() << "}";
        stream << (index + 1U == trials.size() ? "\n" : ",\n");
    }
    stream << "  ]\n}\n";
}

void write_validation(const std::filesystem::path& path,
                      const std::vector<NamedResult>& results) {
    std::ofstream stream(path);
    if (!stream) {
        throw std::runtime_error("cannot write validation: " +
                                 path.string());
    }
    stream << std::setprecision(17) << "{\n  \"runs\": [\n";
    for (std::size_t index = 0; index < results.size(); ++index) {
        const auto& item = results.at(index);
        const auto& result = item.result;
        stream << "    {\n"
               << "      \"file\": \"" << item.file << "\",\n"
               << "      \"trial\": \"" << item.trial << "\",\n"
               << "      \"proposal\": \"" << item.proposal << "\",\n"
               << "      \"order\": \"" << item.order << "\",\n"
               << "      \"records\": " << result.records << ",\n"
               << "      \"alive_records\": " << result.alive_records
               << ",\n"
               << "      \"negative_records\": "
               << result.negative_records << ",\n"
               << "      \"signed_sum_d\": " << result.signed_sum_d
               << ",\n"
               << "      \"absolute_sum_d\": " << result.absolute_sum_d
               << ",\n"
               << "      \"alive_absolute_sum_d\": "
               << result.alive_absolute_sum_d << ",\n"
               << "      \"direct_projection\": "
               << item.direct_projection << ",\n"
               << "      \"sum_residual\": " << item.sum_residual
               << ",\n"
               << "      \"max_alive_identity_residual\": "
               << result.max_alive_identity_residual << ",\n"
               << "      \"elapsed_seconds\": "
               << result.elapsed_seconds << ",\n"
               << "      \"paths_per_second\": "
               << result.paths_per_second << "\n"
               << "    }";
        stream << (index + 1U == results.size() ? "\n" : ",\n");
    }
    stream << "  ]\n}\n";
}

std::vector<int> slice_fields(std::size_t mask, std::size_t sites) {
    std::vector<int> fields(sites, -1);
    for (std::size_t site = 0; site < sites; ++site) {
        if (((mask >> (sites - 1U - site)) & 1U) != 0U) {
            fields.at(site) = +1;
        }
    }
    return fields;
}

void write_guide_validation(const std::filesystem::path& path,
                            const audit::HubbardModel& model,
                            const std::vector<NamedTrial>& trials) {
    if (model.sites() > 4) {
        return;
    }
    const audit::FockOracle oracle(model);
    const auto exact = oracle.dominant_guide();
    double exact_max_residual = 0.0;
    std::ofstream stream(path);
    if (!stream) {
        throw std::runtime_error("cannot write guide validation: " +
                                 path.string());
    }
    stream << std::setprecision(17)
           << "{\n"
           << "  \"guide\": \"dominant eigenvector of the symmetric Trotter slice\",\n"
           << "  \"eigenvalue\": " << exact.eigenvalue << ",\n"
           << "  \"trials\": [\n";
    for (std::size_t trial_index = 0; trial_index < trials.size();
         ++trial_index) {
        const auto& trial = trials.at(trial_index);
        const auto approximate = oracle.slater_vector(trial.state);
        std::vector<std::vector<double>> states;
        states.push_back(approximate);
        const std::size_t configurations =
            std::size_t{1} << model.sites();
        for (std::size_t mask = 0; mask < configurations; ++mask) {
            states.push_back(oracle.apply_path_to_state(
                slice_fields(mask, model.sites()), 1, approximate));
        }
        std::vector<double> approximate_normalizations;
        approximate_normalizations.reserve(states.size());
        for (const auto& state : states) {
            exact_max_residual = std::max(
                exact_max_residual,
                std::abs(oracle.guide_slice_normalization(
                             exact.vector, state) -
                         exact.eigenvalue));
            approximate_normalizations.push_back(
                oracle.guide_slice_normalization(approximate, state));
        }
        const auto [minimum, maximum] = std::minmax_element(
            approximate_normalizations.begin(),
            approximate_normalizations.end());
        const double mean =
            std::accumulate(approximate_normalizations.begin(),
                            approximate_normalizations.end(), 0.0) /
            static_cast<double>(approximate_normalizations.size());
        double variance = 0.0;
        for (const double value : approximate_normalizations) {
            variance += (value - mean) * (value - mean);
        }
        variance /= static_cast<double>(approximate_normalizations.size());
        stream << "    {\"name\": \"" << trial.name
               << "\", \"normalization_min\": " << *minimum
               << ", \"normalization_max\": " << *maximum
               << ", \"normalization_mean\": " << mean
               << ", \"normalization_std\": " << std::sqrt(variance)
               << "}";
        stream << (trial_index + 1U == trials.size() ? "\n" : ",\n");
    }
    stream << "  ],\n"
           << "  \"exact_guide_max_normalization_residual\": "
           << exact_max_residual << "\n"
           << "}\n";
}

int enumerate_command(const Options& options) {
    const auto model = make_model(options);
    const std::size_t slices = size_value(options, "slices", 2);
    const std::filesystem::path output = value(options, "output", "");
    if (output.empty()) {
        throw std::invalid_argument("enumerate requires --output");
    }
    std::filesystem::create_directories(output);

    std::vector<NamedTrial> trials;
    for (const auto& name :
         split(value(options, "trials", "rhf_x,rhf_y,uhf"))) {
        trials.push_back(make_trial(name, model));
    }
    write_metadata(output / "metadata.json", model, slices, trials);
    write_guide_validation(output / "guide_validation.json", model,
                           trials);

    const auto proposals = split(value(options, "proposals", "site,joint"));
    const auto orders =
        split(value(options, "orders", "row,reverse,sublattice"));
    const audit::FockOracle oracle(model);
    std::vector<NamedResult> results;
    for (const auto& trial : trials) {
        for (const auto& proposal : proposals) {
            const bool joint = proposal == "joint";
            if (!joint && proposal != "site") {
                throw std::invalid_argument("unknown proposal: " + proposal);
            }
            const auto active_orders =
                joint ? std::vector<std::string>{"na"} : orders;
            for (const auto& order_name : active_orders) {
                audit::SiteOrderCode order_code =
                    audit::SiteOrderCode::NotApplicable;
                std::vector<std::size_t> site_order =
                    model.row_major_order();
                if (!joint) {
                    auto order = make_order(order_name, model);
                    order_code = order.first;
                    site_order = std::move(order.second);
                }
                const audit::ProposalKind proposal_value =
                    joint ? audit::ProposalKind::JointSlice
                          : audit::ProposalKind::SiteBySite;
                const audit::ProposalCode proposal_code =
                    joint ? audit::ProposalCode::JointSlice
                          : audit::ProposalCode::SiteBySite;
                const std::string stem = trial.name + "_" + proposal + "_" +
                                         order_name;
                const std::string file = "paths_" + stem + ".bin";
                std::cout << "begin " << stem << '\n' << std::flush;
                const audit::PathEvaluator evaluator(
                    model, trial.state, site_order, proposal_value);
                audit::EnumerationOptions enumeration;
                enumeration.slices = slices;
                enumeration.trial_code = trial.code;
                enumeration.proposal_code = proposal_code;
                enumeration.site_order_code = order_code;
                enumeration.output_path = (output / file).string();
                enumeration.progress_updates =
                    size_value(options, "progress-updates", 16);
                auto result =
                    audit::enumerate_paths(evaluator, enumeration);
                const double direct = oracle.projected_amplitude(
                    trial.state, trial.state, slices);
                const double residual =
                    std::abs(result.signed_sum_d - direct);
                results.push_back({file, trial.name, proposal, order_name,
                                   result, direct, residual});
                std::cout << "done " << stem << ": " << result.records
                          << " paths, residual=" << residual
                          << ", alive=" << result.alive_records << '\n'
                          << std::flush;
                write_validation(output / "validation.json", results);
            }
        }
    }
    return 0;
}

int replay_command(const Options& options) {
    const auto model = make_model(options);
    const std::size_t slices = size_value(options, "slices", 1);
    const auto trial = make_trial(value(options, "trial", "rhf_x"), model);
    const std::string proposal_name =
        value(options, "proposal", "site");
    const bool joint = proposal_name == "joint";
    if (!joint && proposal_name != "site") {
        throw std::invalid_argument("unknown proposal: " + proposal_name);
    }
    const auto order = make_order(value(options, "order", "row"), model);
    const std::size_t stabilization_interval =
        size_value(options, "stabilize-every", 5);
    const audit::PathEvaluator evaluator(
        model, trial.state, order.second,
        joint ? audit::ProposalKind::JointSlice
              : audit::ProposalKind::SiteBySite,
        stabilization_interval);
    const std::string output = value(options, "output", "trace.csv");
    audit::PathSummary summary;
    const auto field_file = options.find("fields-file");
    if (field_file != options.end()) {
        const auto fields = audit::read_text_fields(field_file->second);
        if (fields.size() != slices * model.sites()) {
            throw std::invalid_argument(
                "text field count does not match slices times sites");
        }
        summary =
            audit::replay_fields(evaluator, fields, slices, true, output);
    } else {
        summary = audit::replay_config(
            evaluator, uint64_value(options, "config-id"), slices, true,
            output);
    }
    std::cout << std::setprecision(17)
              << "alive=" << static_cast<int>(summary.alive)
              << " final_overlap=" << summary.final_overlap
              << " log_q=" << summary.log_q_prop
              << " log_weight=" << summary.log_w_ratio
              << " first_rejected_step="
              << (summary.first_rejected_step ==
                          std::numeric_limits<std::size_t>::max()
                      ? -1
                      : static_cast<long long>(
                            summary.first_rejected_step))
              << " trace=" << output << '\n';
    return 0;
}

int batch_replay_command(const Options& options) {
    const auto model = make_model(options);
    const std::size_t slices = size_value(options, "slices", 1);
    audit::TrialState initial = make_trial(
        value(options, "trial", "rhf_x"), model
    ).state;
    audit::TrialState guide = initial;
    std::vector<std::size_t> site_order;
    const auto trial_manifest = options.find("trial-manifest");
    if (trial_manifest != options.end()) {
        const auto trial_dir =
            std::filesystem::path(trial_manifest->second).parent_path();
        const SiteMap site_map =
            read_site_map(trial_dir / "site_map.dat", model);
        initial = audit::TrialState::from_orbitals(
            "I",
            alf_to_cpp(
                audit::read_real_orbitals(
                    (trial_dir / "trial_I_up.dat").string(),
                    model.sites(), model.n_up()
                ),
                site_map
            ),
            alf_to_cpp(
                audit::read_real_orbitals(
                    (trial_dir / "trial_I_down.dat").string(),
                    model.sites(), model.n_down()
                ),
                site_map
            )
        );
        guide = audit::TrialState::from_orbitals(
            "T",
            alf_to_cpp(
                audit::read_real_orbitals(
                    (trial_dir / "trial_T_up.dat").string(),
                    model.sites(), model.n_up()
                ),
                site_map
            ),
            alf_to_cpp(
                audit::read_real_orbitals(
                    (trial_dir / "trial_T_down.dat").string(),
                    model.sites(), model.n_down()
                ),
                site_map
            )
        );
        site_order = site_map.cpp_by_alf;
    } else {
        site_order =
            make_order(value(options, "order", "row"), model).second;
    }
    const std::string proposal_name = value(options, "proposal", "site");
    if (proposal_name != "site") {
        throw std::invalid_argument(
            "batch replay requires --proposal site");
    }
    const std::string manifest = value(options, "manifest", "");
    const std::string steps_output =
        value(options, "steps-output", "");
    const std::string masks_output =
        value(options, "masks-output", "");
    if (manifest.empty() || steps_output.empty() ||
        masks_output.empty()) {
        throw std::invalid_argument(
            "batch-replay requires --manifest, --steps-output, "
            "and --masks-output");
    }
    const audit::PathEvaluator evaluator(
        model, initial, guide, site_order,
        audit::ProposalKind::SiteBySite,
        size_value(options, "stabilize-every", 5));
    const auto rows = audit::read_batch_manifest(manifest);
    audit::run_batch_replay(
        evaluator, slices, rows, steps_output, masks_output,
        size_value(options, "progress-updates", 20));
    std::cout << "PASS: batch replay wrote " << rows.size()
              << " paths to " << steps_output << " and "
              << masks_output << '\n';
    return 0;
}

int verify_command(const Options& options) {
    const std::filesystem::path directory = value(options, "results", "");
    if (directory.empty()) {
        throw std::invalid_argument("verify requires --results");
    }
    std::size_t files = 0;
    for (const auto& entry :
         std::filesystem::directory_iterator(directory)) {
        const auto filename = entry.path().filename().string();
        if (!entry.is_regular_file() ||
            filename.rfind("paths_", 0) != 0 ||
            entry.path().extension() != ".bin") {
            continue;
        }
        audit::PathRecordReader reader(entry.path().string());
        const auto& header = reader.header();
        if (header.actual_records != header.expected_records) {
            throw std::runtime_error("incomplete path file: " + filename);
        }
        const auto model = audit::HubbardModel::square_periodic(
            header.lx, header.ly, header.hopping, header.interaction,
            header.dt, header.n_up, header.n_down);
        const auto trial = make_trial(trial_name(header.trial), model);
        const audit::PathEvaluator evaluator(
            model, trial.state, order_from_code(header.site_order, model),
            proposal_kind(header.proposal));
        const double initial_overlap =
            evaluator.initial_state().summary.initial_overlap;
        const double common =
            static_cast<double>(header.slices) *
            std::log(model.slice_constant());
        std::uint64_t count = 0;
        double max_identity_residual = 0.0;
        audit::PathRecord record;
        while (reader.read(record)) {
            if (record.alive) {
                const double residual = std::abs(
                    record.log_q + record.log_abs_weight + common +
                    std::log(std::abs(initial_overlap)) -
                    record.log_abs_d);
                max_identity_residual =
                    std::max(max_identity_residual, residual);
            }
            ++count;
        }
        if (count != header.actual_records ||
            max_identity_residual > 1.0e-9) {
            throw std::runtime_error("path verification failed: " +
                                     filename);
        }
        ++files;
        std::cout << "verified " << filename << ": " << count
                  << " records, max_identity_residual="
                  << max_identity_residual << '\n'
                  << std::flush;
    }
    if (files == 0) {
        throw std::runtime_error("no paths_*.bin files found");
    }
    std::cout << "PASS: verified " << files << " path files\n";
    return 0;
}

int replay_archive_command(const Options& options) {
    const auto archive_index_path = std::filesystem::path(
        required_value(options, "archive-index")
    );
    const auto sample_manifest_path = std::filesystem::path(
        required_value(options, "sample-manifest")
    );
    const auto selected_path = std::filesystem::path(
        required_value(options, "selected-projection")
    );
    const auto trial_manifest_path = std::filesystem::path(
        required_value(options, "trial-manifest")
    );
    const auto field_order_path = std::filesystem::path(
        required_value(options, "field-order")
    );
    const auto summary_path = std::filesystem::path(
        required_value(options, "summary-output")
    );
    const bool summary_only = options.find("summary-only") != options.end();
    const auto prefix_path = summary_only
        ? std::filesystem::path()
        : std::filesystem::path(required_value(options, "prefix-output"));
    if (value(options, "eref-mode", "") != "constant") {
        throw std::invalid_argument(
            "replay-archive supports only --eref-mode constant"
        );
    }
    const double reference_energy =
        real_value(options, "eref-value",
                   std::numeric_limits<double>::quiet_NaN());
    if (!std::isfinite(reference_energy)) {
        throw std::invalid_argument(
            "replay-archive requires finite --eref-value"
        );
    }
    const std::size_t stabilization_interval =
        size_value(options, "stabilize-every", 5);
    if (stabilization_interval == 0) {
        throw std::invalid_argument(
            "--stabilize-every must be positive"
        );
    }

    const std::string field_order = read_text_file(field_order_path);
    for (const std::string& required : {
             "\"validated\": true",
             "\"storage_order\": \"time_slice_major_then_alf_site\"",
             "\"physical_time_direction\": \"right_boundary_to_left_boundary\"",
             "\"slice_split\": \"K/2-V-K/2\"",
             "\"up_exponent\": \"+gamma*x\"",
             "\"down_exponent\": \"-gamma*x\""}) {
        if (field_order.find(required) == std::string::npos) {
            throw std::runtime_error(
                "field-order contract is not validated/exact"
            );
        }
    }
    const std::string selected = read_text_file(selected_path);
    const auto selected_ltrot = static_cast<std::size_t>(
        json_number(selected, "ltrot_star")
    );
    const double selected_theta = json_number(selected, "theta_star");
    const double selected_dt = json_number(selected, "dt");
    const double selected_beta = json_number(selected, "beta");
    const double center_raw =
        selected_theta / selected_dt +
        selected_beta / (2.0 * selected_dt);
    const std::size_t center_slice =
        static_cast<std::size_t>(std::llround(center_raw));
    if (std::abs(center_raw - static_cast<double>(center_slice)) >
            1.0e-12 ||
        selected_ltrot != static_cast<std::size_t>(std::llround(
            (2.0 * selected_theta + selected_beta) / selected_dt
        ))) {
        throw std::runtime_error(
            "selected projection has inconsistent slice counts"
        );
    }

    const std::string archive_index_text =
        read_text_file(archive_index_path);
    const bool chain11_layout = archive_index_text.find(
        "\"sample_id_layout\": \"chain11_sequence49\""
    ) != std::string::npos;
    const auto entries = read_archive_index(archive_index_path);
    const auto requested = read_sample_manifest(sample_manifest_path);
    audit::ArchiveReader first_reader(entries.front().path.string());
    const auto first_header = first_reader.header();
    if (first_header.ltrot != selected_ltrot ||
        std::abs(first_header.theta - selected_theta) > 1.0e-12 ||
        std::abs(first_header.dt - selected_dt) > 1.0e-14 ||
        std::abs(first_header.beta - selected_beta) > 1.0e-14) {
        throw std::runtime_error(
            "archive header differs from selected projection"
        );
    }
    const auto model = audit::HubbardModel::square_periodic(
        first_header.lx, first_header.ly, first_header.hopping,
        first_header.interaction, first_header.dt,
        first_header.n_up, first_header.n_down
    );

    const auto trial_dir = trial_manifest_path.parent_path();
    const SiteMap site_map =
        read_site_map(trial_dir / "site_map.dat", model);
    const auto initial = audit::TrialState::from_orbitals(
        "I",
        alf_to_cpp(
            audit::read_real_orbitals(
                (trial_dir / "trial_I_up.dat").string(),
                model.sites(), model.n_up()
            ),
            site_map
        ),
        alf_to_cpp(
            audit::read_real_orbitals(
                (trial_dir / "trial_I_down.dat").string(),
                model.sites(), model.n_down()
            ),
            site_map
        )
    );
    const auto guide = audit::TrialState::from_orbitals(
        "T",
        alf_to_cpp(
            audit::read_real_orbitals(
                (trial_dir / "trial_T_up.dat").string(),
                model.sites(), model.n_up()
            ),
            site_map
        ),
        alf_to_cpp(
            audit::read_real_orbitals(
                (trial_dir / "trial_T_down.dat").string(),
                model.sites(), model.n_down()
            ),
            site_map
        )
    );

    std::map<std::uint64_t, LoadedArchiveRecord> loaded;
    for (const auto& entry : entries) {
        audit::ArchiveReader reader(entry.path.string());
        const auto& header = reader.header();
        if (header.ensemble_code != entry.ensemble_code ||
            header.lx != first_header.lx ||
            header.ly != first_header.ly ||
            header.n_up != first_header.n_up ||
            header.n_down != first_header.n_down ||
            header.ltrot != first_header.ltrot ||
            header.nfield != first_header.nfield ||
            header.selected_projection_sha256 !=
                first_header.selected_projection_sha256 ||
            header.trial_manifest_sha256 !=
                first_header.trial_manifest_sha256) {
            throw std::runtime_error(
                "archive index contains incompatible headers"
            );
        }
        audit::ArchiveRecordView record;
        while (reader.read(record)) {
            const auto wanted = requested.find(record.sample_id);
            if (wanted == requested.end()) {
                continue;
            }
            const auto encoded_ensemble = static_cast<std::uint8_t>(
                (record.sample_id >> 60U) & 0x0fU
            );
            const auto encoded_chain = static_cast<std::uint32_t>(
                chain11_layout
                    ? ((record.sample_id >> 49U) & 0x7ffU)
                    : ((record.sample_id >> 52U) & 0xffU)
            );
            if (record.chain_id != entry.chain ||
                wanted->second.ensemble_code != entry.ensemble_code ||
                wanted->second.chain != entry.chain ||
                encoded_ensemble != entry.ensemble_code ||
                encoded_chain != entry.chain ||
                !record.endpoint_present ||
                !loaded.emplace(
                    record.sample_id,
                    LoadedArchiveRecord{header, record}
                ).second) {
                throw std::runtime_error(
                    "sample/archive identity conflict"
                );
            }
        }
        if (reader.truncated_tail()) {
            throw std::runtime_error(
                "archive index contains a truncated archive"
            );
        }
    }
    if (loaded.size() != requested.size()) {
        throw std::runtime_error(
            "not every requested sample maps to exactly one archive"
        );
    }

    std::filesystem::create_directories(summary_path.parent_path());
    if (!summary_only) {
        std::filesystem::create_directories(prefix_path.parent_path());
    }
    std::ofstream summary(summary_path);
    if (!summary) {
        throw std::runtime_error("cannot write replay summary");
    }
    audit::write_replay_summary_header(summary);
    std::unique_ptr<audit::PrefixFileWriter> prefixes;
    if (!summary_only) {
        const std::uint64_t prefix_count =
            static_cast<std::uint64_t>(loaded.size()) *
            static_cast<std::uint64_t>(first_header.ltrot);
        prefixes = std::make_unique<audit::PrefixFileWriter>(
            prefix_path.string(), prefix_count
        );
    }
    const std::size_t progress_every =
        std::max<std::size_t>(1, loaded.size() / 20U);
    std::size_t completed = 0;
    for (const auto& [sample_id, item] : loaded) {
        (void)sample_id;
        const auto replay = audit::replay_archive_record(
            item.header, item.record, model, initial, guide,
            site_map.cpp_by_alf, center_slice,
            stabilization_interval, reference_energy
        );
        audit::write_replay_summary_row(summary, item.header, replay);
        if (prefixes) {
            for (const auto& prefix : replay.prefixes) {
                prefixes->write(prefix);
            }
        }
        ++completed;
        if (completed % progress_every == 0 ||
            completed == loaded.size()) {
            summary.flush();
            std::cout << "archive replay " << completed << '/'
                      << loaded.size() << " paths\n" << std::flush;
        }
    }
    if (prefixes) {
        prefixes->finish();
    }
    if (!summary) {
        throw std::runtime_error("failed while writing replay summary");
    }
    return 0;
}

void usage() {
    std::cerr
        << "Usage:\n"
        << "  cpmc_audit enumerate --slices M --output DIR [--trials LIST] "
           "[--proposals LIST] [--orders LIST]\n"
        << "  cpmc_audit replay --slices M --trial NAME "
           "(--config-id ID | --fields-file FILE) --output TRACE.csv "
           "[--stabilize-every 5]\n"
        << "  cpmc_audit batch-replay --slices M --trial NAME "
           "--manifest FILE --steps-output FILE --masks-output FILE "
           "[--stabilize-every 5]\n"
        << "  cpmc_audit export-uhf --lx 4 --ly 4 --t 1 --u 4 --dt 0.05 "
           "--n-up 8 --n-down 8 --initial-up FILE --initial-down FILE "
           "--site-map FILE --output-dir DIR\n"
        << "  cpmc_audit replay-archive --archive-index FILE "
           "--sample-manifest FILE --selected-projection FILE "
           "--trial-manifest FILE --field-order FILE "
           "--summary-output FILE "
           "(--prefix-output FILE | --summary-only) "
           "--eref-mode constant --eref-value E [--stabilize-every 5]\n"
        << "  cpmc_audit verify --results DIR\n";
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc < 2) {
            usage();
            return 2;
        }
        const std::string command = argv[1];
        const auto options = parse_options(argc, argv, 2);
        if (command == "enumerate") {
            return enumerate_command(options);
        }
        if (command == "replay") {
            return replay_command(options);
        }
        if (command == "batch-replay") {
            return batch_replay_command(options);
        }
        if (command == "export-uhf") {
            return export_uhf_command(options);
        }
        if (command == "replay-archive") {
            return replay_archive_command(options);
        }
        if (command == "verify") {
            return verify_command(options);
        }
        usage();
        throw std::invalid_argument("unknown command: " + command);
    } catch (const std::exception& error) {
        std::cerr << "ERROR: " << error.what() << '\n';
        return 1;
    }
}
