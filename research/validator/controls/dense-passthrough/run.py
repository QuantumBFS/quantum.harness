#!/usr/bin/env python3
import json
import sys
from pathlib import Path

import numpy as np

input_dir = Path(sys.argv[sys.argv.index("--input-dir") + 1])
out = Path(sys.argv[sys.argv.index("--output") + 1])
instances = []
for path in sorted(input_dir.glob("*.npz")):
    with np.load(path) as data:
        n = data["matrix"].shape[0]
    instances.append({"id": path.stem, "method": "dense", "dimension": n, "sectors": []})
out.write_text(json.dumps({"schema_version": 1, "instances": instances}))
