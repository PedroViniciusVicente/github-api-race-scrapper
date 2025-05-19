from src.auth.get_token import get_github_token
from src.github_searches.search import search_github_issues
from src.github_searches.metadata_filter import filter_metadata
from src.github_searches.keyword_filter import filter_by_keywords

def main():

    # 1. Get GitHub token from environment variable
    token = get_github_token()
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}"
    }

    # 2. Search GitHub issues using the token
    search_github_issues(headers)

    # 3. Filter metadata from the search results
    filter_metadata(headers)

    # 4. Filter repositories by keywords
    filter_by_keywords()

if __name__ == "__main__":
    main()
