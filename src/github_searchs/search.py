import requests
from urllib.parse import quote
import re
import json

def search_github_issues(token, search_phrases, languages):
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}"
    }

    repos_set = {}

    for lang in languages:
        print(f"\n🔎 Buscando por issues em projetos com linguagem {lang}...\n")
        
        for phrase in search_phrases:
            print(f"Buscando pela frase exata: '{phrase}'")
            
            strategy_1_query = f'"{phrase}" language:{lang} in:title,body state:closed is:issue' # ou is:pr
            words = phrase.split()

            if len(words) > 1:
                proximity_terms = [f'"{words[i]}..{words[i+1]}"' for i in range(len(words) - 1)]
                strategy_2_query = f'{" ".join(proximity_terms)} language:{lang} in:title,body state:closed is:issue'
            else:
                strategy_2_query = strategy_1_query

            query_to_use = strategy_2_query
            print(f"Query sendo usada: {query_to_use}")

            url = f"https://api.github.com/search/issues?q={quote(query_to_use)}&sort=updated&order=desc&per_page=25"
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                results = response.json()
                raw_count = results['total_count']
                print(f"Total encontrado pela API: {raw_count} issues\n")

                for issue in results['items']:
                    title = issue['title'].lower()
                    issue_url = issue['url']
                    issue_response = requests.get(issue_url, headers=headers)

                    if issue_response.status_code == 200:
                        issue_data = issue_response.json()
                        body = issue_data.get('body', '').lower() if issue_data.get('body') else ''
                        phrase_lower = phrase.lower()

                        if phrase_lower in title or phrase_lower in body:
                            repo_url = issue['repository_url']
                            if repo_url not in repos_set:
                                repo_response = requests.get(repo_url, headers=headers)
                                if repo_response.status_code == 200:
                                    repos_set[repo_url] = repo_response.json()

            else:
                print(f"Erro {response.status_code}: {response.text}")

    with open("data_repos/repos.json", "w", encoding="utf-8") as f:
        json.dump(list(repos_set.values()), f, indent=2, ensure_ascii=False)
        print(f"\n💾 Dados de {len(repos_set)} repositórios salvos em repos.json")
