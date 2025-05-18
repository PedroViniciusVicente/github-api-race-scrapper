# 2. Filters the repos searched by the GitHub API based
LANGUAGES = [
    "javascript",
    # 'typescript',
]
SEARCH_PHRASES = [
    "event race",
    # "race event",
    "race condition",
    # "eventrace",
    # "flaky",
]

# 3. Filters the metadata of the repos searched
METADATA_FILTERS = {
    "min_stars": 10,
    "min_forks": 0,
    "updated_since": "2022-01-01T00:00:00Z",
}

# 4. Filters the repos by keywords
KEYWORDS = [
    "async",
    "await",
    "Promise",
    "setTimeout",
    "setInterval"
]
EXTENSIONS = [".js", ".ts", ".jsx", ".tsx"]
MAX_FILES = 20