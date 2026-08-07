CXX := icpx
CXXFLAGS := -O3 -fp-model=precise -std=c++17 -Wall -Wextra -Wpedantic -Werror -Iinclude
LDFLAGS := -qmkl=sequential

BUILD := build
SRC := $(wildcard src/*.cpp)
CORE_SRC := $(filter-out src/main.cpp,$(SRC))
TEST_SRC := $(wildcard tests/test_*.cpp)
TEST_BINS := $(patsubst tests/%.cpp,$(BUILD)/%,$(TEST_SRC))

.PHONY: all clean test test_dense test_hubbard test_trial test_path_evaluator test_fock_oracle test_io test_enumerator test_replay

all: $(BUILD)/cpmc_audit

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/cpmc_audit: $(SRC) | $(BUILD)
	$(CXX) $(CXXFLAGS) $(SRC) -o $@ $(LDFLAGS)

$(BUILD)/test_%: tests/test_%.cpp $(CORE_SRC) | $(BUILD)
	$(CXX) $(CXXFLAGS) $< $(CORE_SRC) -o $@ $(LDFLAGS)

test: $(TEST_BINS)
	@for t in $(TEST_BINS); do "$$t"; done

test_dense: $(BUILD)/test_dense_matrix
	$(BUILD)/test_dense_matrix

test_hubbard: $(BUILD)/test_hubbard
	$(BUILD)/test_hubbard

test_trial: $(BUILD)/test_trial
	$(BUILD)/test_trial

test_path_evaluator: $(BUILD)/test_path_evaluator
	$(BUILD)/test_path_evaluator

test_fock_oracle: $(BUILD)/test_fock_oracle
	$(BUILD)/test_fock_oracle

test_io: $(BUILD)/test_io
	$(BUILD)/test_io

test_enumerator: $(BUILD)/test_enumerator
	$(BUILD)/test_enumerator

test_replay: $(BUILD)/test_replay
	$(BUILD)/test_replay

clean:
	rm -rf $(BUILD)
