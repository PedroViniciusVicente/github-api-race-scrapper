import requests
from urllib.parse import quote
import json

from config.filters import LANGUAGES
from config.filters import SEARCH_PHRASES

def search_github_issues(headers):
    collected_issues = []

    for lang in LANGUAGES:
        print(f"\n🔎 Buscando por issues em projetos com linguagem {lang}...\n")
        
        for phrase in SEARCH_PHRASES:
            print(f"Buscando pela frase exata: '{phrase}'")

            strategy_1_query = f'"{phrase}" language:{lang} in:title,body state:closed is:issue'
            words = phrase.split()

            if len(words) > 1:
                proximity_terms = [f'"{words[i]}..{words[i+1]}"' for i in range(len(words) - 1)]
                strategy_2_query = f'{" ".join(proximity_terms)} language:{lang} in:title,body state:closed is:issue'
            else:
                strategy_2_query = strategy_1_query

            query_to_use = strategy_1_query
            
            print(f"Query sendo usada: {query_to_use}")

            url = f"https://api.github.com/search/issues?q={quote(query_to_use)}&sort=updated&order=desc&per_page=25"
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                results = response.json()
                raw_count = results['total_count']
                print(f"Total encontrado pela API: {raw_count} issues\n")

                for issue in results['items']:
                    title = issue['title'].lower()
                    body_preview = issue.get('body', '') or ''
                    phrase_lower = phrase.lower()
                    found = phrase_lower in title.lower() or phrase_lower in body_preview.lower()

                    # Se não encontrou na prévia, mas o body parece truncado, faz o fetch completo
                    body_needs_checking = '...' in body_preview or not found

                    if body_needs_checking:
                        issue_url = issue['url']
                        issue_response = requests.get(issue_url, headers=headers)

                        if issue_response.status_code == 200:
                            issue_data = issue_response.json()
                            body_full = issue_data.get('body', '').lower()
                            found = phrase_lower in title.lower() or phrase_lower in body_full
                        else:
                            print(f"⚠️ Erro ao buscar issue completa: {issue_response.status_code}")
                            continue

                    if found:
                        collected_issues.append({
                            "repo_url": issue["repository_url"],
                            "repo_name": "/".join(issue["repository_url"].split("/")[-2:]),
                            "issue_url": issue["html_url"],
                            "author": issue["user"]["login"],
                            "search_phrase": phrase
                        })

            else:
                print(f"Erro {response.status_code}: {response.text}")

    with open("data_repos/issues.json", "w", encoding="utf-8") as f:
        json.dump(collected_issues, f, indent=2, ensure_ascii=False)
        print(f"\n💾 {len(collected_issues)} issues salvas em data_repos/issues.json")
