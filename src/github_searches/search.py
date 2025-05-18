import requests
from urllib.parse import quote
import json

from config.filters import LANGUAGES
from config.filters import SEARCH_PHRASES

def search_github_issues(headers):
    collected_issues = []
    seen_issue_urls = set()


    for lang in LANGUAGES:
        print(f"\n🔎 Buscando por issues em projetos com a linguagem {lang}...\n")
        
        quoted_phrases = [f'"{phrase}"' for phrase in SEARCH_PHRASES]
        search_terms_query_part = " OR ".join(quoted_phrases)

        query_str = f"({search_terms_query_part}) language:{lang} in:title,body state:closed is:issue"
        url = f"https://api.github.com/search/issues?q={quote(query_str)}&sort=updated&order=desc&per_page=30"
        response = requests.get(url, headers=headers)

        print(f"Query sendo usada: {query_str}")

        if response.status_code == 200:
            results = response.json()
            raw_count = results['total_count']
            print(f"Total encontrado pela API: {raw_count} issues\n")

            for issue in results['items']:
                issue_html_url = issue["html_url"]
                title_lower = issue['title'].lower()
                body_preview_original = issue.get('body', '') or ''
                body_preview_lower = body_preview_original.lower()
                

                matching_phrases_for_this_issue = []
                
                for phrase in SEARCH_PHRASES:
                    phrase_lower = phrase.lower()
                    
                    found_in_preview = phrase_lower in title_lower or phrase_lower in body_preview_lower
                    
                    needs_full_body_check = (not found_in_preview) or ('...' in body_preview_original)
                    
                    current_phrase_found = found_in_preview

                    if needs_full_body_check:
                        issue_api_url = issue['url']


                        if 'full_body_fetched' not in issue: # Fetch only once
                            issue['full_body_fetched'] = True # Mark as fetched
                            issue['full_body_content'] = None
                            if ('...' in body_preview_original and not found_in_preview) or not found_in_preview:
                                issue_api_url = issue['url']
                                issue_response = requests.get(issue_api_url, headers=headers)
                                if issue_response.status_code == 200:
                                    issue_data = issue_response.json()
                                    issue['full_body_content'] = (issue_data.get('body', '') or '').lower()
                                else:
                                    print(f"⚠️ Erro ao buscar issue completa {issue_api_url}: {issue_response.status_code}")
                        
                        if issue.get('full_body_content'):
                            current_phrase_found = phrase_lower in title_lower or phrase_lower in issue['full_body_content']

                    if current_phrase_found:
                        matching_phrases_for_this_issue.append(phrase)

                if matching_phrases_for_this_issue:
                    if issue_html_url not in seen_issue_urls:
                        collected_issues.append({
                            "repo_url": issue["repository_url"],
                            "repo_name": "/".join(issue["repository_url"].split("/")[-2:]),
                            "issue_url": issue_html_url,
                            "author": issue["user"]["login"],
                            "matched_phrases": matching_phrases_for_this_issue # Lista de frases
                            # "search_phrase": matching_phrases_for_this_issue[0] # Ou apenas a primeira
                        })
                        seen_issue_urls.add(issue_html_url)

        else:
            print(f"Erro na busca pela API para query combinada, status {response.status_code}: {response.text}")


    with open("data_repos/issues.json", "w", encoding="utf-8") as f:
        json.dump(collected_issues, f, indent=2, ensure_ascii=False)
        print(f"\n💾 {len(collected_issues)} issues salvas em data_repos/issues.json")
