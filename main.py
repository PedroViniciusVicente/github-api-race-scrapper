from auth.get_token import get_github_token
from github_search import search_github_issues
from repo_metadata_filter import filter_metadata

def main():

    search_phrases = [
        # "event race",
        # "race event",
        "race condition",
        # "eventrace",
        # "flaky",
    ]

    languages = [
        "javascript",
        # 'typescript',
    ]

    # Get the GitHub token from the environment variable
    token = get_github_token()

    # Search for repos based on search_phrases and languages
    search_github_issues(token, search_phrases, languages)

    # Filter the searched repos based on stars and last commit date
    filter_metadata()

    # Filter the searched repos based on the presence of keyswords like async await, etc

if __name__ == "__main__":
    main()
