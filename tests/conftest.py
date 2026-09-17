from hypothesis import settings

# Derandomized so a CI failure reproduces locally from the same examples.
# No deadline: these are correctness properties, not performance tests. The generated data is
# fixed, so a per-example time limit is the one thing that could make a run pass or fail by
# machine load alone (one unreproduced failure of this kind was seen in Wave 1; see the report).
settings.register_profile("default", derandomize=True, max_examples=100, deadline=None)
settings.load_profile("default")
