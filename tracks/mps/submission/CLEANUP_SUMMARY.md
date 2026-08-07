# Cleanup Summary

The 472 MB original tree was inventoried. The PR uses selective migration:
caches, temporary directories, raw chains, archives, PID/job markers and large
checkpoint bodies are excluded; compact evidence, failures, metadata, hashes,
source, tests and configs are retained. Original unique data was not deleted.
