from src.auth.get_token import get_github_token
from src.github_searches.search import search_github_issues
from src.github_searches.metadata_filter import filter_metadata
from src.github_searches.keyword_filter import filter_by_keywords
from src.github_searches.pr_search import search_github_prs
from src.github_searches.filter_search import analyze_projects_with_criteria

def main():

    # 1. Get GitHub token from environment variable
    token = get_github_token()
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}"
    }

    # 2. Search GitHub issues using the token
    # search_github_issues(headers)

    # 3. Filter metadata from the search results
    # filter_metadata(headers)

    # 4. Filter repositories by keywords
    # filter_by_keywords()


    # Search for PRs
    # search_github_prs(headers)

    # try:
    #     prs = search_github_prs(headers, save_checkpoint=True)
    #     print(f"✅ Successfully collected {len(prs)} PRs")
    # except KeyboardInterrupt:
    #     print("🛑 Interrupted by user - progress has been saved")
    # except Exception as e:
    #     print(f"❌ Error: {e}")

    stats = analyze_projects_with_criteria(
        headers=headers,
        input_json_path="data_repos/race_condition_prs-2.json",
        output_json_path="data_repos/filtered_race_condition_prs-2.json"
    )

if __name__ == "__main__":
    main()
