# import base64
# import json
# import time
# import re
# import requests
# from typing import List, Dict
# from datetime import datetime

# GITHUB_TOKEN = "your_github_token_here"

# GRAPHQL_URL = "https://api.github.com/graphql"
# REST_API_URL = "https://api.github.com"

# PR_DESCRIPTION_TERMS = [
#     "race condition",
#     "event race",
#     "concurrency bug",
#     "flaky test",
#     "race bug",
# ]

# TEST_FILE_PATTERNS = [".test.", ".spec.", "_test.", "_spec.", "/test/", "/tests/"]
# ASYNC_KEYWORDS = ["async", "await", "promise"]

# HEADERS = {
#     "Authorization": f"Bearer {GITHUB_TOKEN}",
#     "Accept": "application/vnd.github.v3+json"
# }

# def graphql_search_prs() -> List[Dict]:
#     query_terms = " OR ".join(PR_DESCRIPTION_TERMS)
#     query = f"""
#     query {{
#       search(
#         query: \"is:pr is:merged language:JavaScript stars:>=10 {query_terms}\",
#         type: ISSUE,
#         first: 50
#       ) {{
#         nodes {{
#           ... on PullRequest {{
#             title
#             body
#             url
#             number
#             baseRefName
#             repository {{
#               name
#               owner {{ login }}
#               stargazerCount
#             }}
#           }}
#         }}
#       }}
#     }}
#     """
#     response = requests.post(GRAPHQL_URL, json={"query": query}, headers=HEADERS)
#     response.raise_for_status()
#     return response.json()["data"]["search"]["nodes"]

# def is_test_file(filename: str) -> bool:
#     return any(pattern in filename.lower() for pattern in TEST_FILE_PATTERNS)

# def file_contains_async_terms(content: str) -> bool:
#     return any(term in content for term in ASYNC_KEYWORDS)

# def get_changed_files(owner: str, repo: str, pr_number: int) -> List[Dict]:
#     url = f"{REST_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files"
#     response = requests.get(url, headers=HEADERS)
#     response.raise_for_status()
#     return response.json()

# def get_file_content(owner: str, repo: str, path: str, ref: str) -> str:
#     url = f"{REST_API_URL}/repos/{owner}/{repo}/contents/{path}?ref={ref}"
#     response = requests.get(url, headers=HEADERS)
#     if response.status_code != 200:
#         return ""
#     data = response.json()
#     if data.get("encoding") == "base64":
#         return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
#     return ""

# def main():
#     print("🔍 Searching GitHub PRs using GraphQL...")
#     prs = graphql_search_prs()
#     matches = []

#     for pr in prs:
#         owner = pr["repository"]["owner"]["login"]
#         repo = pr["repository"]["name"]
#         pr_number = pr["url"].split("/")[-1]
#         ref = pr["baseRefName"]

#         try:
#             files = get_changed_files(owner, repo, pr_number)
#         except Exception as e:
#             print(f"⚠️ Failed to get files for PR {pr['url']}: {e}")
#             continue

#         for file in files:
#             filename = file["filename"]
#             if not is_test_file(filename):
#                 continue

#             try:
#                 content = get_file_content(owner, repo, filename, ref)
#                 if file_contains_async_terms(content):
#                     matches.append({
#                         "url": pr["url"],
#                         "title": pr["title"],
#                         "repo": f"{owner}/{repo}",
#                         "test_file": filename,
#                         "matched_term": [term for term in PR_DESCRIPTION_TERMS if term in pr["title"].lower() or term in pr["body"].lower()]
#                     })
#                     break
#             except Exception as e:
#                 print(f"⚠️ Error reading file {filename}: {e}")

#         time.sleep(1)  # To respect GitHub rate limits

#     print(f"✅ Found {len(matches)} matching PRs")
#     with open("matching_prs.json", "w", encoding="utf-8") as f:
#         json.dump(matches, f, indent=2, ensure_ascii=False)

# if __name__ == "__main__":
#     main()
