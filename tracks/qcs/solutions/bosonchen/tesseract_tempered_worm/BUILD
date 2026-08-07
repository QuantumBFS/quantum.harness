load("@rules_cc//cc:defs.bzl", "cc_binary", "cc_library", "cc_test")

package(default_visibility = ["//visibility:public"])

cc_library(
    name = "tempered_worm",
    srcs = ["tempered_worm.cc"],
    hdrs = ["tempered_worm.h"],
    copts = [
        "-O3",
        "-std=c++20",
    ],
)

cc_test(
    name = "tempered_worm_test",
    srcs = ["tempered_worm_test.cc"],
    copts = [
        "-O3",
        "-std=c++20",
    ],
    deps = [
        ":tempered_worm",
        "@gtest",
        "@gtest//:gtest_main",
    ],
)

cc_binary(
    name = "phase0",
    srcs = ["phase0_main.cc"],
    copts = [
        "-O3",
        "-std=c++20",
    ],
    deps = [
        ":tempered_worm",
        "//src:libtesseract",
        "//src:libutils",
        "@nlohmann_json//:json",
        "@stim//:stim_lib",
    ],
)
