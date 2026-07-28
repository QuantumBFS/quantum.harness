#!/usr/bin/env python3
import json
import sys
from pathlib import Path

out = Path(sys.argv[sys.argv.index("--output") + 1])
out.write_text(json.dumps({"schema_version": 1, "instances": []}))
