# Cleanup Policy

Inventory, hash, classify, check references, dry-run, then remove only caches,
temporary files, byte-identical duplicates, or reproducible generated output.
Keep source, tests, configs, manifests, negative results, checkpoint metadata,
seeds, hashes, failure summaries, and unique data. Do not delete a unique
checkpoint without explicit confirmation and a verified backup.
