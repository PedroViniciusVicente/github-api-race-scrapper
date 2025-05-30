import requests
from urllib.parse import quote, urlparse, parse_qs
import json
import time
import re

from config.filters import (
    LANGUAGES,
    TEST_FILE_IDENTIFIERS,
    PR_DESCRIPTION_TERMS
)

def get_next_page_url(response):
    """Extract next page URL from Link header"""
    links = response.headers.get('Link', '')
    for link in links.split(', '):
        if 'rel="next"' in link:
            return link[link.index('<') + 1:link.index('>')]
    return None

def is_js_file(filename):
    """Check if the file is a JavaScript file"""
    return filename.endswith('.js') or filename.endswith('.jsx')

def search_github_prs(headers):
    collected_prs = []
    seen_pr_urls = set()
    
    # Add counters for statistics
    total_prs_found = 0
    prs_with_js_files = 0
    prs_with_terms = 0
    prs_matching_both = 0
    prs_processed = 0

    for lang in LANGUAGES:
        print(f"\n🔎 Buscando por pull requests em projetos com a linguagem {lang}...\n")
        
        # Create search query for PRs with race condition related terms
        quoted_phrases = [f'"{phrase}"' for phrase in PR_DESCRIPTION_TERMS]
        search_terms_query_part = " OR ".join(quoted_phrases)

        # Add extension filter to the query to reduce false positives
        query_str = f"({search_terms_query_part}) language:{lang} is:pr is:merged"
        base_url = f"https://api.github.com/search/issues?q={quote(query_str)}&sort=updated&order=desc&per_page=100"
        
        print(f"Query sendo usada: {query_str}")
        
        url = base_url
        page = 1
        max_pages = 10  # Limit to 1000 PRs per language (10 pages * 100 per page)

        while url and page <= max_pages:
            print(f"\nBuscando página {page}...")
            response = requests.get(url, headers=headers)
            
            # Handle rate limiting
            if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
                remaining = int(response.headers['X-RateLimit-Remaining'])
                if remaining == 0:
                    reset_time = int(response.headers['X-RateLimit-Reset'])
                    wait_time = reset_time - time.time() + 1
                    if wait_time > 0:
                        print(f"Atingido limite da API. Aguardando {int(wait_time)} segundos...")
                        time.sleep(wait_time)
                        response = requests.get(url, headers=headers)

            if response.status_code == 200:
                results = response.json()
                
                if page == 1:
                    raw_count = results['total_count']
                    print(f"Total encontrado pela API: {raw_count} pull requests")
                    total_prs_found += raw_count

                for pr in results['items']:
                    prs_processed += 1
                    print(f"\nProcessando PR {prs_processed}/{raw_count}: {pr['html_url']}")
                    
                    pr_html_url = pr["html_url"]
                    if pr_html_url in seen_pr_urls:
                        continue

                    # Check for terms in title and description first
                    title = pr["title"].lower()
                    body = (pr.get('body', '') or '').lower()
                    matching_terms = []
                    
                    for term in PR_DESCRIPTION_TERMS:
                        term_lower = term.lower()
                        if term_lower in title or term_lower in body:
                            matching_terms.append(term)
                    
                    # Only proceed with API calls if we found matching terms
                    if not matching_terms:
                        continue

                    pr_api_url = pr['url'].replace('issues', 'pulls')
                    pr_response = requests.get(pr_api_url, headers=headers)
                    
                    if pr_response.status_code == 403:  # Handle rate limiting
                        remaining = int(pr_response.headers['X-RateLimit-Remaining'])
                        if remaining == 0:
                            reset_time = int(pr_response.headers['X-RateLimit-Reset'])
                            wait_time = reset_time - time.time() + 1
                            if wait_time > 0:
                                print(f"Atingido limite da API. Aguardando {int(wait_time)} segundos...")
                                time.sleep(wait_time)
                                pr_response = requests.get(pr_api_url, headers=headers)
                    
                    if pr_response.status_code != 200:
                        print(f"⚠️ Erro ao buscar PR completa {pr_api_url}: {pr_response.status_code}")
                        continue

                    pr_data = pr_response.json()
                    
                    # Get the files changed in the PR
                    files_url = f"{pr_api_url}/files"
                    files_response = requests.get(files_url, headers=headers)
                    
                    if files_response.status_code == 403:  # Handle rate limiting
                        remaining = int(files_response.headers['X-RateLimit-Remaining'])
                        if remaining == 0:
                            reset_time = int(files_response.headers['X-RateLimit-Reset'])
                            wait_time = reset_time - time.time() + 1
                            if wait_time > 0:
                                print(f"Atingido limite da API. Aguardando {int(wait_time)} segundos...")
                                time.sleep(wait_time)
                                files_response = requests.get(files_url, headers=headers)
                    
                    if files_response.status_code != 200:
                        print(f"⚠️ Erro ao buscar arquivos da PR {files_url}: {files_response.status_code}")
                        continue

                    files_data = files_response.json()
                    
                    # Check for JavaScript files
                    js_files = []
                    for file in files_data:
                        file_name = file['filename'].lower()
                        if is_js_file(file_name):
                            js_files.append(file_name)

                    # Check for terms in title and description
                    title = pr["title"].lower()
                    description = (pr_data.get('body', '') or '').lower()
                    matching_terms = []
                    
                    for term in PR_DESCRIPTION_TERMS:
                        term_lower = term.lower()
                        if term_lower in title or term_lower in description:
                            matching_terms.append(term)

                    # Update statistics
                    has_js_files = len(js_files) > 0
                    has_terms = len(matching_terms) > 0

                    if has_js_files:
                        prs_with_js_files += 1
                        print(f"✅ PR tem arquivos JavaScript: {pr_html_url}")
                        print(f"   Arquivos JavaScript encontrados: {', '.join(js_files)}")

                    if has_terms:
                        prs_with_terms += 1
                        print(f"✅ PR tem termos de race condition: {pr_html_url}")
                        print(f"   Termos encontrados: {', '.join(matching_terms)}")

                    if has_js_files and has_terms:
                        prs_matching_both += 1
                        collected_prs.append({
                            "repo_url": pr["repository_url"],
                            "repo_name": "/".join(pr["repository_url"].split("/")[-2:]),
                            "pr_url": pr_html_url,
                            "author": pr["user"]["login"],
                            "js_files": js_files,
                            "matched_terms": matching_terms,
                            "title": pr["title"],
                            "body": pr_data.get('body', '')
                        })
                        seen_pr_urls.add(pr_html_url)

                # Get next page URL from Link header
                url = get_next_page_url(response)
                page += 1
                
                # Add a small delay to avoid hitting rate limits too quickly
                time.sleep(1)
            else:
                print(f"Erro na busca pela API para query combinada, status {response.status_code}: {response.text}")
                break

    # Print statistics
    print("\n📊 Estatísticas da busca:")
    print(f"Total de PRs encontrados: {total_prs_found}")
    print(f"Total de PRs processados: {prs_processed}")
    print(f"PRs com arquivos JavaScript: {prs_with_js_files}")
    print(f"PRs com termos de race condition: {prs_with_terms}")
    print(f"PRs que satisfazem ambas as condições: {prs_matching_both}")

    # Save results
    with open("data_repos/race_condition_prs.json", "w", encoding="utf-8") as f:
        json.dump(collected_prs, f, indent=2, ensure_ascii=False)
        print(f"\n💾 {len(collected_prs)} pull requests salvas em data_repos/race_condition_prs.json") 