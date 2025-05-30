import requests
from urllib.parse import quote
import json
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import re

from config.filters import (
    LANGUAGES,
    PR_DESCRIPTION_TERMS,
    TEST_FILE_PATTERNS, # Fixed test file detection - use filename patterns instead of content keywords
)

def get_next_page_url(response):
    links = response.headers.get('Link', '')
    for link in links.split(', '):
        if 'rel="next"' in link:
            return link[link.index('<') + 1:link.index('>')]
    return None

def is_js_file(filename):
    return filename.lower().endswith(('.js', '.jsx', '.ts', '.tsx'))

def is_test_file(filename):
    """Check if filename indicates it's a test file"""
    filename_lower = filename.lower()
    return any(pattern in filename_lower for pattern in TEST_FILE_PATTERNS)

def daterange(start_date, end_date, delta_days):
    while start_date < end_date:
        yield start_date, min(start_date + timedelta(days=delta_days), end_date)
        start_date += timedelta(days=delta_days)

def handle_rate_limit(response):
    """Handle GitHub API rate limiting"""
    if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
        remaining = int(response.headers['X-RateLimit-Remaining'])
        if remaining == 0:
            reset_time = int(response.headers['X-RateLimit-Reset'])
            wait_time = reset_time - time.time() + 1
            if wait_time > 0:
                print(f"⏳ Rate limit reached. Waiting {int(wait_time)} seconds...")
                time.sleep(wait_time)
                return True
    return False

def fetch_pr_files(pr_api_url, headers):
    """Fetch PR files with error handling"""
    files_url = f"{pr_api_url}/files"
    files_response = requests.get(files_url, headers=headers)
    
    if files_response.status_code != 200:
        return []
    
    files_data = files_response.json()
    
    # Filter for JavaScript test files
    js_test_files = [
        f['filename'] for f in files_data 
        if is_js_file(f['filename']) and is_test_file(f['filename'])
    ]
    
    return js_test_files

def process_pr(pr, headers):
    """Process individual PR to check if it matches criteria"""
    title = pr["title"].lower()
    body = (pr.get('body', '') or '').lower()
    
    # Check if PR has any of the target terms
    matching_terms = [
        term for term in PR_DESCRIPTION_TERMS 
        if term.lower() in title or term.lower() in body
    ]
    
    if not matching_terms:
        return None
    
    # Get PR details
    pr_api_url = pr['url'].replace('issues', 'pulls')
    pr_response = requests.get(pr_api_url, headers=headers)
    
    if pr_response.status_code != 200:
        return None
    
    pr_data = pr_response.json()
    
    # Check for JavaScript test files
    js_test_files = fetch_pr_files(pr_api_url, headers)
    
    if not js_test_files:
        return None
    
    return {
        "repo_url": pr["repository_url"],
        "repo_name": "/".join(pr["repository_url"].split("/")[-2:]),
        "pr_url": pr['html_url'],
        "author": pr["user"]["login"],
        "js_test_files": js_test_files,
        "matched_terms": matching_terms,
        "title": pr["title"],
        "body": pr_data.get('body', ''),
        "created_at": pr["created_at"],
        "merged_at": pr_data.get("merged_at")
    }

def search_github_prs(headers, max_workers=5):
    """
    Search GitHub PRs with optimizations:
    - Better error handling
    - Reduced API calls
    - Cleaner logic
    - Progress tracking
    """
    collected_prs = []
    seen_pr_urls = set()
    
    # Statistics
    stats = {
        'total_found': 0,
        'processed': 0,
        'with_terms': 0,
        'with_js_test_files': 0,
        'matching_all_criteria': 0
    }
    
    start_date = datetime(2020, 1, 1)
    end_date = datetime(2024, 12, 31)
    delta_days = 7  # Can be increased to 30 for fewer API calls
    
    for lang in LANGUAGES:
        print(f"\n🔎 Searching PRs in {lang} projects...\n")
        
        # Build search query
        quoted_phrases = [f'"{phrase}"' for phrase in PR_DESCRIPTION_TERMS]
        search_terms_query = " OR ".join(quoted_phrases)
        
        for start, end in daterange(start_date, end_date, delta_days):
            created_filter = f"created:{start.strftime('%Y-%m-%d')}..{end.strftime('%Y-%m-%d')}"
            query_str = f"({search_terms_query}) language:{lang} is:pr is:merged {created_filter}"
            
            base_url = f"https://api.github.com/search/issues?q={quote(query_str)}&sort=updated&order=desc&per_page=100"
            
            print(f"📅 Period: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
            
            url = base_url
            page = 1
            
            while url:
                print(f"📄 Fetching page {page}...")
                response = requests.get(url, headers=headers)
                
                # Handle rate limiting
                if handle_rate_limit(response):
                    continue
                
                if response.status_code != 200:
                    print(f"❌ API Error: {response.status_code} - {response.text}")
                    break
                
                results = response.json()
                
                if page == 1:
                    total_in_period = min(results.get('total_count', 0), 1000)
                    stats['total_found'] += total_in_period
                    print(f"📊 Found {total_in_period} PRs in this period")
                
                # Process PRs
                for pr in results.get('items', []):
                    if pr['html_url'] in seen_pr_urls:
                        continue
                    
                    stats['processed'] += 1
                    
                    if stats['processed'] % 50 == 0:
                        print(f"⚡ Processed {stats['processed']} PRs so far...")
                    
                    processed_pr = process_pr(pr, headers)
                    
                    if processed_pr:
                        stats['with_terms'] += 1
                        
                        if processed_pr['js_test_files']:
                            stats['with_js_test_files'] += 1
                            stats['matching_all_criteria'] += 1
                            
                            collected_prs.append(processed_pr)
                            seen_pr_urls.add(pr['html_url'])
                            
                            print(f"✅ Match found: {pr['html_url']}")
                            print(f"   📁 Test files: {processed_pr['js_test_files'][:3]}{'...' if len(processed_pr['js_test_files']) > 3 else ''}")
                            print(f"   🏷️ Terms: {processed_pr['matched_terms']}")
                    
                    # Small delay to be respectful to API
                    time.sleep(0.1)
                
                url = get_next_page_url(response)
                page += 1
                time.sleep(1)  # Delay between pages
    
    # Print final statistics
    print("\n" + "="*60)
    print("📊 FINAL STATISTICS")
    print("="*60)
    print(f"Total PRs found by search: {stats['total_found']}")
    print(f"Total PRs processed: {stats['processed']}")
    print(f"PRs with target terms: {stats['with_terms']}")
    print(f"PRs with JS test files: {stats['with_js_test_files']}")
    print(f"PRs matching ALL criteria: {stats['matching_all_criteria']}")
    print(f"Success rate: {(stats['matching_all_criteria']/max(stats['processed'], 1)*100):.2f}%")
    
    # Save results
    output_file = "data_repos/race_condition_prs.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "search_date": datetime.now().isoformat(),
                "total_prs_collected": len(collected_prs),
                "search_criteria": {
                    "date_range": "2020-01-01 to 2024-12-31",
                    "terms": PR_DESCRIPTION_TERMS,
                    "languages": LANGUAGES,
                    "test_file_patterns": TEST_FILE_PATTERNS
                },
                "statistics": stats
            },
            "pull_requests": collected_prs
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to {output_file}")
    print(f"🎯 Found {len(collected_prs)} PRs matching all criteria!")
    
    return collected_prs