import json
import requests
from base64 import b64decode
from src.auth.get_token import get_github_token

from config.filters import KEYWORDS
from config.filters import EXTENSIONS
from config.filters import MAX_FILES

# Autenticação
TOKEN = get_github_token()
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {TOKEN}"
}

def keyword_found_in_repo(owner, repo_name):
    url = f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/HEAD?recursive=1"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"⚠️ Falha ao buscar arquivos de {owner}/{repo_name}")
        return False

    tree = response.json().get("tree", [])
    count = 0

    for item in tree:
        path = item.get("path", "")
        if item.get("type") != "blob":
            continue
        if not any(path.endswith(ext) for ext in EXTENSIONS):
            continue

        raw_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}"
        file_resp = requests.get(raw_url, headers=HEADERS)

        if file_resp.status_code != 200:
            continue

        file_data = file_resp.json()
        if file_data.get("encoding") != "base64":
            continue

        try:
            content = b64decode(file_data.get("content", "")).decode("utf-8", errors="ignore")
        except Exception:
            continue

        if any(keyword.lower() in content.lower() for keyword in KEYWORDS):
            print(f"🔍 Keyword encontrada em: {path}")
            return True

        count += 1
        if count >= MAX_FILES:
            break

    return False

def filter_by_keywords():
    try:
        with open("data_repos/filtered_repos.json", "r", encoding="utf-8") as f:
            issues = json.load(f)
    except FileNotFoundError:
        print("Arquivo filtered_repos.json não encontrado.")
        return

    final_issues = []

    for issue in issues:
        repo_name = issue["repo_name"]  # Ex: "user/repo"
        try:
            owner, name = repo_name.split("/")
        except ValueError:
            print(f"⚠️ Formato de repo_name inválido: {repo_name}")
            continue

        print(f"📦 Analisando {repo_name}...")

        if keyword_found_in_repo(owner, name):
            final_issues.append(issue)
            print("✅ Incluído (keywords encontradas)\n")
        else:
            print("❌ Excluído (keywords não encontradas)\n")

    with open("data_repos/final_repos.json", "w", encoding="utf-8") as out:
        json.dump(final_issues, out, indent=2, ensure_ascii=False)

    print(f"\n📊 Issues finais com keywords no repositório: {len(final_issues)}/{len(issues)}")
    print("📁 Resultado salvo em final_repos.json\n")

# if __name__ == "__main__":
#     filter_by_keywords()
