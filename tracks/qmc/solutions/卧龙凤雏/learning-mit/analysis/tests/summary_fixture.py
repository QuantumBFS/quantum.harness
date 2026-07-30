def summary_fixture():
    return {
        "schema_version": 1,
        "status": "xy_reproduced_diii_candidate",
        "exploratory": True,
        "team": "卧龙凤雏",
        "run": {
            "elapsed_seconds": 3512.4,
            "ordinary_stop_seconds": 3300,
            "hard_stop_seconds": 5100,
            "widths": [8, 12, 16, 20, 24, 28, 32],
            "streams": 8,
        },
        "xy": {
            "theta_pi": 0.5,
            "reference_window": [0.20, 0.28],
            "bracket": [0.24, 0.27],
            "evidence": [
                {"phi_pi": 0.18, "score": -0.8},
                {"phi_pi": 0.21, "score": -0.4},
                {"phi_pi": 0.24, "score": -0.1},
                {"phi_pi": 0.25, "score": 0.1},
                {"phi_pi": 0.27, "score": 0.5},
                {"phi_pi": 0.30, "score": 0.9},
            ],
        },
        "diii": {
            "theta_pi": 0.45,
            "bracket": [0.18, 0.22],
            "evidence": [
                {"phi_pi": 0.06, "score": -0.9},
                {"phi_pi": 0.10, "score": -0.7},
                {"phi_pi": 0.14, "score": -0.4},
                {"phi_pi": 0.18, "score": -0.1},
                {"phi_pi": 0.22, "score": 0.2},
                {"phi_pi": 0.26, "score": 0.5},
                {"phi_pi": 0.30, "score": 0.7},
                {"phi_pi": 0.34, "score": 0.9},
            ],
        },
        "entanglement": {
            "arcs": [
                {
                    "label": "L=16, φ/π=0.18",
                    "width": 16,
                    "phi_pi": 0.18,
                    "points": [[1, 0.4], [2, 0.7], [4, 1.0], [8, 1.2]],
                },
                {
                    "label": "L=32, φ/π=0.22",
                    "width": 32,
                    "phi_pi": 0.22,
                    "points": [[1, 0.5], [2, 0.9], [4, 1.4], [8, 2.1], [16, 2.6]],
                },
            ],
            "coefficients": [
                {"phi_pi": 0.18, "width": 16, "v": 0.01, "c_prime": 0.02, "c": 0.20},
                {"phi_pi": 0.22, "width": 32, "v": 0.03, "c_prime": 0.18, "c": 0.31},
            ],
        },
        "casimir": {
            "widths": [8, 12, 16, 20, 24, 28, 32],
            "gamma": [5.837, 8.755, 11.674, 14.594, 17.514, 20.434, 23.354],
            "fitted": [5.836, 8.756, 11.674, 14.594, 17.514, 20.434, 23.354],
            "residuals": [0.001, -0.001, 0.0, 0.0, 0.0, 0.0, 0.0],
            "amplitude": 0.41,
            "amplitude_interval": [0.32, 0.50],
            "correction": "l3",
        },
        "bootstrap": {
            "amplitude_samples": [0.34, 0.37, 0.39, 0.41, 0.42, 0.44, 0.48],
            "effective_sample_size": 82.0,
        },
        "anisotropy": {
            "delta": 0.37,
            "spatial": [[2, 0.31], [3, 0.21], [4, 0.16], [6, 0.10], [8, 0.075]],
            "temporal": [[16, 0.036], [24, 0.024], [32, 0.018]],
            "alpha": 1.25,
            "alpha_interval": [1.02, 1.49],
            "alpha_stable": True,
            "window_estimates": [
                {"window": "L/8–3L/8", "alpha": 1.25, "error": 0.10},
                {"window": "L/6–L/3", "alpha": 1.21, "error": 0.12},
                {"window": "drop first block", "alpha": 1.29, "error": 0.13},
            ],
        },
        "central_charge": {
            "published": True,
            "value": 0.328,
            "interval": [0.24, 0.43],
        },
        "negative_control": {
            "born_mean": 1.83,
            "iid_mean": 2.14,
            "z_score": 5.2,
            "physical": False,
        },
        "runtime": {
            "allocation": [
                ["Oracles/benchmark", 6],
                ["XY scan", 15],
                ["DIII coarse", 15],
                ["Refinement", 17],
                ["Analysis/report", 5],
            ]
        },
        "oracles": {
            "dense_probability_error": 2.1e-14,
            "dense_covariance_error": 3.2e-13,
            "weak_limit_error": 4.0e-14,
            "passed": True,
        },
        "hashes": {
            "manifest": "a" * 64,
            "blocks": "b" * 64,
        },
    }
