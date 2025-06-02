# 2. Filters the repos searched by the GitHub API based
LANGUAGES = [
    "javascript",
    # 'typescript',
]

# Terms to identify test files
# TEST_FILE_IDENTIFIERS = [
#     "describe",
#     "it",
#     "test",
# ]

# Terms to identify race conditions and concurrency issues in PR descriptions
PR_DESCRIPTION_TERMS = [
    "race condition",
    "event race",
    "concurrency bug",
    "flaky test",
    "race bug",
]

TEST_FILE_PATTERNS = [
    ".test.", ".spec.", "_test.", "_spec.", 
    "/test/", "/tests/", "__tests__", 
    "test.", "spec."  # files starting with test/spec
]

# Original search phrases kept for reference
SEARCH_PHRASES = [
    "event race",
    "event races",
    # "eventrace",
    # "eventraces",
    # "event-race",
    # "event-races",
    # "race event",
    # "racing event",
    "racing events",
    "race condition",
    # "race-condition",
    # "race conditions",
    "racing condition",
    # "racing-conditions",
    # "racing test",
    # "racing-test",
    # "race-test",
    # "flaky",
    # "concurrency",
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
    # "setTimeout",
    # "setInterval"
]
EXTENSIONS = [".js", ".ts", ".jsx", ".tsx"]
MAX_FILES = 20