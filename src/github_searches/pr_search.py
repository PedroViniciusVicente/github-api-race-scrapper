import requests
from urllib.parse import quote
import json
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import RequestException, ConnectionError, Timeout
import logging

from config.filters import (
    LANGUAGES,
    PR_DESCRIPTION_TERMS
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Fixed test file detection - use filename patterns instead of content keywords
TEST_FILE_PATTERNS = [
    ".test.", ".spec.", "_test.", "_spec.", 
    "/test/", "/tests/", "__tests__", 
    "test.", "spec."  # files starting with test/spec
]

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

def create_session_with_retries():
    """Create a requests session with retry strategy"""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=5,  # Total number of retries
        backoff_factor=2,  # Wait time between retries (exponential backoff)
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry
        allowed_methods=["HEAD", "GET", "OPTIONS"]  # Only retry safe methods
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def safe_api_request(session, url, headers, max_retries=3, base_delay=1):
    """Make API request with robust error handling and retries"""
    for attempt in range(max_retries):
        try:
            response = session.get(url, headers=headers, timeout=30)
            
            # Handle rate limiting
            if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
                remaining = int(response.headers['X-RateLimit-Remaining'])
                if remaining == 0:
                    reset_time = int(response.headers['X-RateLimit-Reset'])
                    wait_time = reset_time - time.time() + 1
                    if wait_time > 0:
                        print(f"⏳ Rate limit reached. Waiting {int(wait_time)} seconds...")
                        time.sleep(wait_time)
                        continue
            
            return response
            
        except (ConnectionError, Timeout, RequestException) as e:
            wait_time = base_delay * (2 ** attempt)  # Exponential backoff
            print(f"⚠️ Network error on attempt {attempt + 1}/{max_retries}: {str(e)}")
            
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"❌ Failed after {max_retries} attempts")
                raise e
    
    return None

def fetch_pr_files(pr_api_url, session, headers):
    """Fetch PR files with robust error handling"""
    files_url = f"{pr_api_url}/files"
    
    try:
        files_response = safe_api_request(session, files_url, headers)
        
        if files_response is None or files_response.status_code != 200:
            return []
        
        files_data = files_response.json()
        
        # Filter for JavaScript test files
        js_test_files = [
            f['filename'] for f in files_data 
            if is_js_file(f['filename']) and is_test_file(f['filename'])
        ]
        
        return js_test_files
        
    except Exception as e:
        print(f"⚠️ Error fetching files for {pr_api_url}: {str(e)}")
        return []

def process_pr(pr, session, headers):
    """Process individual PR to check if it matches criteria"""
    try:
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
        pr_response = safe_api_request(session, pr_api_url, headers)
        
        if pr_response is None or pr_response.status_code != 200:
            return None
        
        pr_data = pr_response.json()
        
        # Check for JavaScript test files
        js_test_files = fetch_pr_files(pr_api_url, session, headers)
        
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
        
    except Exception as e:
        print(f"⚠️ Error processing PR {pr.get('html_url', 'unknown')}: {str(e)}")
        return None

def search_github_prs(headers, max_workers=5, save_checkpoint=True):
    """
    Search GitHub PRs with robust error handling and recovery:
    - Network error recovery with retries
    - Connection pooling and session reuse
    - Checkpoint saving for recovery
    - Better error handling and logging
    """
    collected_prs = []
    seen_pr_urls = set()
    
    # Create session with retry strategy
    session = create_session_with_retries()
    
    # Statistics
    stats = {
        'total_found': 0,
        'processed': 0,
        'with_terms': 0,
        'with_js_test_files': 0,
        'matching_all_criteria': 0,
        'errors': 0
    }
    
    start_date = datetime(2024, 6, 26)
    end_date = datetime(2025, 5, 1)
    delta_days = 7  # Can be increased to 30 for fewer API calls
    
    checkpoint_file = "data_repos/checkpoint.json"
    
    # Load checkpoint if exists
    try:
        with open(checkpoint_file, 'r') as f:
            checkpoint = json.load(f)
            collected_prs = checkpoint.get('collected_prs', [])
            seen_pr_urls = set(checkpoint.get('seen_pr_urls', []))
            stats = checkpoint.get('stats', stats)
            print(f"📂 Loaded checkpoint: {len(collected_prs)} PRs already collected")
    except FileNotFoundError:
        print("🆕 Starting fresh search (no checkpoint found)")
    
    try:
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
                    
                    try:
                        response = safe_api_request(session, url, headers)
                        
                        if response is None or response.status_code != 200:
                            if response:
                                print(f"❌ API Error: {response.status_code} - {response.text}")
                            stats['errors'] += 1
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
                                
                                # Save checkpoint every 50 PRs
                                if save_checkpoint:
                                    save_checkpoint_data(checkpoint_file, collected_prs, seen_pr_urls, stats)
                            
                            processed_pr = process_pr(pr, session, headers)
                            
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
                            time.sleep(0.2)
                        
                        url = get_next_page_url(response)
                        page += 1
                        time.sleep(2)  # Increased delay between pages
                    
                    except Exception as e:
                        print(f"❌ Error processing page {page}: {str(e)}")
                        stats['errors'] += 1
                        time.sleep(5)  # Wait longer after errors
                        break
    
    except KeyboardInterrupt:
        print("\n🛑 Search interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        stats['errors'] += 1
    finally:
        # Always save final results
        save_final_results(collected_prs, stats)
        
        # Clean up checkpoint file
        try:
            import os
            os.remove(checkpoint_file)
        except:
            pass
    
    return collected_prs

def save_checkpoint_data(checkpoint_file, collected_prs, seen_pr_urls, stats):
    """Save checkpoint data for recovery"""
    try:
        checkpoint_data = {
            'collected_prs': collected_prs,
            'seen_pr_urls': list(seen_pr_urls),
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        }
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Failed to save checkpoint: {str(e)}")

def save_final_results(collected_prs, stats):
    """Save final results with statistics"""
    # Print final statistics
    print("\n" + "="*60)
    print("📊 FINAL STATISTICS")
    print("="*60)
    print(f"Total PRs found by search: {stats['total_found']}")
    print(f"Total PRs processed: {stats['processed']}")
    print(f"PRs with target terms: {stats['with_terms']}")
    print(f"PRs with JS test files: {stats['with_js_test_files']}")
    print(f"PRs matching ALL criteria: {stats['matching_all_criteria']}")
    print(f"Errors encountered: {stats['errors']}")
    print(f"Success rate: {(stats['matching_all_criteria']/max(stats['processed'], 1)*100):.2f}%")
    
    # Save results
    output_file = "data_repos/race_condition_prs.json"
    try:
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
        
    except Exception as e:
        print(f"❌ Error saving results: {str(e)}")
        # Try to save with simpler format
        try:
            backup_file = "data_repos/race_condition_prs_backup.json"
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(collected_prs, f, indent=2, ensure_ascii=False)
            print(f"💾 Backup saved to {backup_file}")
        except:
            print("❌ Failed to save backup as well")