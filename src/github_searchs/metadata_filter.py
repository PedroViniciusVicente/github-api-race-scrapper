import json
from datetime import datetime

# Filtros de exemplo
FILTERS = {
    "min_stars": 50,
    "max_stars": 5000,
    "min_forks": 10,
    "updated_since": "2024-01-01T00:00:00Z",
}

def repo_matches_filters(repo, filters):
    if filters.get("min_stars") and repo.get("stargazers_count", 0) < filters["min_stars"]:
        return False
    if filters.get("max_stars") and repo.get("stargazers_count", 0) > filters["max_stars"]:
        return False
    if filters.get("min_forks") and repo.get("forks_count", 0) < filters["min_forks"]:
        return False
    if filters.get("updated_since"):
        pushed_at = repo.get("pushed_at")
        if pushed_at and pushed_at < filters["updated_since"]:
            return False
    return True

def filter_metadata():
    try:
        with open("data_repos/repos.json", "r", encoding="utf-8") as f:
            repos = json.load(f)
    except FileNotFoundError:
        print("Arquivo repos.json não encontrado.")
        return

    filtered = [r for r in repos if repo_matches_filters(r, FILTERS)]

    print(f"\n🔍 Filtros aplicados: {FILTERS}")
    print(f"✅ Repositórios que passaram nos filtros: {len(filtered)}/{len(repos)}")

    with open("data_repos/filtered_repos.json", "w", encoding="utf-8") as out:
        json.dump(filtered, out, indent=2)

    print("📁 Resultado salvo em filtered_repos.json\n")

