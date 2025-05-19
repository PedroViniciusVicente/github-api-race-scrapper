import json
import requests
from config.filters import METADATA_FILTERS

def repo_matches_filters(repo_metadata, filters):
    if filters.get("min_stars") and repo_metadata.get("stargazers_count", 0) < filters["min_stars"]:
        return False
    if filters.get("min_forks") and repo_metadata.get("forks_count", 0) < filters["min_forks"]:
        return False
    if filters.get("updated_since"):
        pushed_at = repo_metadata.get("pushed_at")
        if pushed_at and pushed_at < filters["updated_since"]:
            return False
    return True

def filter_metadata(headers):
    try:
        with open("data_repos/repos.json", "r", encoding="utf-8") as f:
            issues = json.load(f)
    except FileNotFoundError:
        print("Arquivo repos.json não encontrado.")
        return

    filtered = []
    checked_repos = {}

    for issue in issues:
        repo_api_url = issue["repo_url"]

        # Evita buscar o mesmo repositório várias vezes
        if repo_api_url in checked_repos:
            repo_metadata = checked_repos[repo_api_url]
        else:
            response = requests.get(repo_api_url, headers=headers)
            if response.status_code != 200:
                print(f"⚠️ Falha ao buscar metadados de {repo_api_url}: {response.status_code}")
                continue
            repo_metadata = response.json()
            checked_repos[repo_api_url] = repo_metadata

        if repo_matches_filters(repo_metadata, METADATA_FILTERS):
            filtered.append(issue)

    print(f"\n🔍 Filtros aplicados: {METADATA_FILTERS}")
    print(f"✅ Issues que passaram nos filtros de metadados: {len(filtered)}/{len(issues)}")

    with open("data_repos/filtered_repos.json", "w", encoding="utf-8") as out:
        json.dump(filtered, out, indent=2, ensure_ascii=False)

    print("📁 Resultado salvo em filtered_repos.json\n")
