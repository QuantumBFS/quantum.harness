#include "tempered_worm.h"

#include <cmath>

#include "gtest/gtest.h"

namespace tw = tempered_worm;

TEST(TemperedWormModelTest, DetectsKernelAndLogicalMoves) {
  tw::Model model(
      2, 1,
      {
          {1.0, {0}, 1},
          {2.0, {0}, 0},
          {1.5, {0, 1}, 0},
          {2.5, {0, 1}, 1},
      });
  EXPECT_TRUE(model.is_kernel_move({0, 1}));
  EXPECT_TRUE(model.is_kernel_move({2, 3}));
  EXPECT_FALSE(model.is_kernel_move({0, 2}));
  EXPECT_EQ(model.logical_mask_of({0, 1}), 1);
}

TEST(TemperedWormCycleLibraryTest, BuildsExactSectorChangingMoves) {
  tw::Model model(1, 1, {{1.0, {0}, 1}, {2.0, {0}, 0}});
  tw::CycleBuildConfig config;
  config.random_attempts = 0;
  config.logical_seed_attempts = 0;
  auto library = tw::CycleLibrary::build(model, config);
  ASSERT_EQ(library.moves.size(), 1);
  EXPECT_EQ(library.moves[0].errors, (std::vector<uint32_t>{0, 1}));
  EXPECT_EQ(library.moves[0].logical_mask, 1);
  EXPECT_EQ(library.stats.logical_sector_moves, 1);
}

TEST(TemperedWormSamplerTest, RecoversTwoStatePosteriorAtBetaOne) {
  tw::Model model(1, 1, {{1.0, {0}, 1}, {2.0, {0}, 0}});
  tw::CycleBuildConfig cycle_config;
  cycle_config.random_attempts = 0;
  cycle_config.logical_seed_attempts = 0;
  auto library = tw::CycleLibrary::build(model, cycle_config);
  auto initial = tw::State::from_errors(model, {0});

  tw::SamplerConfig sampler_config;
  sampler_config.betas = {0.5, 1.0, 2.0};
  sampler_config.burn_in_sweeps = 1000;
  sampler_config.measurement_sweeps = 20000;
  sampler_config.moves_per_sweep = 1;
  sampler_config.seed = 1234;
  auto result =
      tw::sample_logical_sector(model, library, initial, sampler_config);

  double expected = std::exp(-1.0) / (std::exp(-1.0) + std::exp(-2.0));
  double observed =
      static_cast<double>(result.logical_counts.at(1)) / result.target_samples;
  EXPECT_NEAR(observed, expected, 0.03);
  EXPECT_EQ(result.predicted_logical_mask, 1);
  EXPECT_EQ(model.syndrome_of(initial.selected_errors()),
            (std::vector<uint8_t>{1}));
}

TEST(TemperedWormBarTest, RecoversExactTwoSectorFreeEnergyDifference) {
  tw::Model model(1, 1, {{1.0, {0}, 0}, {2.0, {0}, 1}});
  tw::CycleBuildConfig cycle_config;
  cycle_config.random_attempts = 0;
  cycle_config.logical_seed_attempts = 0;
  auto library = tw::CycleLibrary::build(model, cycle_config);
  ASSERT_EQ(library.moves.size(), 1);
  auto reference = tw::State::from_errors(model, {0});

  tw::BarConfig bar_config;
  bar_config.burn_in_sweeps = 0;
  bar_config.measurement_sweeps = 100;
  auto result = tw::compare_logical_sectors_bar(
      model, library, reference, library.moves[0], bar_config);

  EXPECT_NEAR(result.delta_free_energy, 1.0, 1e-10);
  EXPECT_NEAR(result.overlap_score, 1.0, 1e-10);
  EXPECT_EQ(result.local_move_attempts, 0);
}

TEST(TemperedWormAlgebraicBuildTest, ClosesLogicalErrorWithDetectorBasis) {
  tw::Model model(
      2, 1,
      {
          {1.0, {0}, 0},
          {1.0, {1}, 0},
          {2.0, {0, 1}, 1},
      });
  tw::CycleBuildConfig cycle_config;
  cycle_config.random_attempts = 0;
  cycle_config.logical_seed_attempts = 0;
  auto library = tw::CycleLibrary::build(model, cycle_config);
  ASSERT_TRUE(library.moves.empty());

  auto stats = tw::add_algebraic_logical_moves(model, library, 2, 8, 8);

  ASSERT_EQ(library.moves.size(), 1);
  EXPECT_EQ(library.moves[0].errors,
            (std::vector<uint32_t>{0, 1, 2}));
  EXPECT_EQ(library.moves[0].logical_mask, 1);
  EXPECT_EQ(stats.detector_basis_rank, 2);
  EXPECT_EQ(stats.logical_targets_closed, 1);
  EXPECT_EQ(stats.moves_added, 1);
}

TEST(TemperedWormAlgebraicBuildTest, RetainsNonlogicalDependenciesAsLocalMoves) {
  tw::Model model(
      2, 0,
      {
          {1.0, {0}, 0},
          {1.0, {1}, 0},
          {2.0, {0, 1}, 0},
      });
  tw::CycleBuildConfig cycle_config;
  cycle_config.random_attempts = 0;
  cycle_config.logical_seed_attempts = 0;
  auto library = tw::CycleLibrary::build(model, cycle_config);

  auto stats =
      tw::add_algebraic_logical_moves(model, library, 3, 8, 8);

  ASSERT_EQ(library.moves.size(), 1);
  EXPECT_EQ(library.moves[0].errors,
            (std::vector<uint32_t>{0, 1, 2}));
  EXPECT_EQ(library.moves[0].logical_mask, 0);
  EXPECT_EQ(stats.local_dependencies_found, 1);
  EXPECT_EQ(stats.local_moves_added, 1);
}
