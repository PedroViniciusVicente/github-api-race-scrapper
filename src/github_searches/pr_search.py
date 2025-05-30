import requests
from urllib.parse import quote
import json
import time
from datetime import datetime, timedelta

from config.filters import (
    LANGUAGES,
    TEST_FILE_IDENTIFIERS,
    PR_DESCRIPTION_TERMS
)

def get_next_page_url(response):
    links = response.headers.get('Link', '')
    for link in links.split(', '):
        if 'rel="next"' in link:
            return link[link.index('<') + 1:link.index('>')]
    return None

def is_js_file(filename):
    return filename.endswith('.js') or filename.endswith('.jsx')

def daterange(start_date, end_date, delta_days):
    while start_date < end_date:
        yield start_date, min(start_date + timedelta(days=delta_days), end_date)
        start_date += timedelta(days=delta_days)

def search_github_prs(headers):
    collected_prs = []
    seen_pr_urls = set()

    total_prs_found = 0
    prs_with_js_files = 0
    prs_with_terms = 0
    prs_matching_both = 0
    prs_processed = 0

    start_date = datetime(2020, 1, 1)
    end_date = datetime(2024, 12, 31)
    delta_days = 7

    for lang in LANGUAGES:
        print(f"\n🔎 Buscando por pull requests em projetos com a linguagem {lang}...\n")

        quoted_phrases = [f'"{phrase}"' for phrase in PR_DESCRIPTION_TERMS]
        search_terms_query_part = " OR ".join(quoted_phrases)

        for start, end in daterange(start_date, end_date, delta_days):
            created_filter = f"created:{start.strftime('%Y-%m-%d')}..{end.strftime('%Y-%m-%d')}"
            query_str = f"({search_terms_query_part}) language:{lang} is:pr is:merged {created_filter}"
            base_url = f"https://api.github.com/search/issues?q={quote(query_str)}&sort=updated&order=desc&per_page=100"

            print(f"Query sendo usada: {query_str}")

            url = base_url
            page = 1

            while url:
                print(f"\nBuscando página {page}...")
                response = requests.get(url, headers=headers)

                if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
                    remaining = int(response.headers['X-RateLimit-Remaining'])
                    if remaining == 0:
                        reset_time = int(response.headers['X-RateLimit-Reset'])
                        wait_time = reset_time - time.time() + 1
                        if wait_time > 0:
                            print(f"Aguardando {int(wait_time)} segundos por limite da API...")
                            time.sleep(wait_time)
                            continue

                if response.status_code != 200:
                    print(f"Erro na busca pela API: {response.status_code} - {response.text}")
                    break

                results = response.json()

                if page == 1:
                    raw_count = min(results.get('total_count', 0), 1000)
                    print(f"Total encontrado pela API (limitado a 1000): {raw_count}")
                    total_prs_found += raw_count

                for pr in results.get('items', []):
                    if pr['html_url'] in seen_pr_urls:
                        continue

                    prs_processed += 1
                    print(f"\nProcessando PR {prs_processed}: {pr['html_url']}")

                    title = pr["title"].lower()
                    body = (pr.get('body', '') or '').lower()
                    matching_terms = [term for term in PR_DESCRIPTION_TERMS if term.lower() in title or term.lower() in body]

                    if not matching_terms:
                        continue

                    pr_api_url = pr['url'].replace('issues', 'pulls')
                    pr_response = requests.get(pr_api_url, headers=headers)

                    if pr_response.status_code != 200:
                        continue

                    pr_data = pr_response.json()

                    files_url = f"{pr_api_url}/files"
                    files_response = requests.get(files_url, headers=headers)

                    if files_response.status_code != 200:
                        continue

                    js_files = [f['filename'].lower() for f in files_response.json() if is_js_file(f['filename'].lower()) and any(identifier in f['filename'].lower() for identifier in TEST_FILE_IDENTIFIERS)]

                    has_js_files = bool(js_files)
                    has_terms = bool(matching_terms)

                    if has_js_files:
                        prs_with_js_files += 1
                        print(f"✅ PR tem arquivos JavaScript: {pr['html_url']}")

                    if has_terms:
                        prs_with_terms += 1

                    if has_js_files and has_terms:
                        prs_matching_both += 1
                        collected_prs.append({
                            "repo_url": pr["repository_url"],
                            "repo_name": "/".join(pr["repository_url"].split("/")[-2:]),
                            "pr_url": pr['html_url'],
                            "author": pr["user"]["login"],
                            "js_files": js_files,
                            "matched_terms": matching_terms,
                            "title": pr["title"],
                            "body": pr_data.get('body', '')
                        })
                        seen_pr_urls.add(pr['html_url'])

                url = get_next_page_url(response)
                page += 1
                time.sleep(1)

    print("\n📊 Estatísticas da busca:")
    print(f"Total de PRs encontrados: {total_prs_found}")
    print(f"Total de PRs processados: {prs_processed}")
    print(f"PRs com arquivos JavaScript: {prs_with_js_files}")
    print(f"PRs com termos: {prs_with_terms}")
    print(f"PRs que satisfazem ambas condições: {prs_matching_both}")

    with open("data_repos/race_condition_prs.json", "w", encoding="utf-8") as f:
        json.dump(collected_prs, f, indent=2, ensure_ascii=False)
        print(f"\n💾 {len(collected_prs)} pull requests salvos em data_repos/race_condition_prs.json")
