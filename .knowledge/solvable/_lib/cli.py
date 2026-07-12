"""Uniform CLI wrapper for oracle scripts."""
import argparse
import json


def oracle_main(compute, params):
    """params: {name: (type, default)}; compute(**kwargs) -> {quantity: value}."""
    p = argparse.ArgumentParser(description=compute.__doc__)
    for name, (typ, default) in params.items():
        p.add_argument(f"--{name}", type=typ, default=default)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    out = compute(**{n: getattr(a, n) for n in params})
    if a.json:
        print(json.dumps(out))
    else:
        for k, v in out.items():
            print(f"{k} = {v}")
