#!/usr/bin/env python3
import json
import sys
from pathlib import Path

input_dir = Path(sys.argv[sys.argv.index("--input-dir") + 1])
out = Path(sys.argv[sys.argv.index("--output") + 1])
instances = []
for path in sorted(input_dir.glob("*.npz")):
    instances.append({"id": path.stem, "method": "character_projectors", "sectors": [{"character": [0], "basis": [[[1.0, 0.0]]], "block": [[[0.0, 0.0]]], "eigenvalues": [0.0]}]})
out.write_text(json.dumps({"schema_version": 1, "instances": instances}))
