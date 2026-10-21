"""Version 1 of the API."""

# ponytail: a constant, not a setting - the version prefix is part of the API
# contract. Mount the app under a path with uvicorn's --root-path instead.
API_V1_PREFIX = "/v1"
