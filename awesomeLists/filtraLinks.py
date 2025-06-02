import json
import requests
import os
import time
import re
from typing import List, Dict, Any
from urllib.parse import urlparse
from dotenv import load_dotenv



class GitHubPRAnalyzer:
    def __init__(self, github_token: str = None):
        """
        Inicializa o analisador com token do GitHub (opcional mas recomendado)
        Para obter um token: https://github.com/settings/tokens
        """
        self.github_token = github_token
        self.session = requests.Session()
        
        if github_token:
            self.session.headers.update({
                'Authorization': f'token {github_token}',
                'Accept': 'application/vnd.github.v3+json'
            })
        
        # Termos para buscar em PR descriptions
        self.pr_description_terms = [
            "race condition",
            "event race", 
            "concurrency bug",
            "flaky test",
            "race bug",
        ]
        
        # Padrões de arquivos de teste
        self.test_file_patterns = [
            ".test.", ".spec.", "_test.", "_spec.", 
            "/test/", "/tests/", "__tests__", 
            "test.", "spec."
        ]
        
        # Keywords para identificar testes e código assíncrono
        self.test_keywords = ["describe(", "it(", "test("]
        self.async_keywords = ["promise", "async"]
    
    def load_repositories(self, json_file: str) -> List[str]:
        """Carrega lista de repositórios do arquivo JSON"""
        try:
            with open(json_file, 'r') as f:
                repos = json.load(f)
            return repos
        except FileNotFoundError:
            print(f"Arquivo {json_file} não encontrado!")
            return []
        except json.JSONDecodeError:
            print(f"Erro ao decodificar JSON do arquivo {json_file}")
            return []
    
    def extract_repo_info(self, github_url: str) -> tuple:
        """Extrai owner e repo name de uma URL do GitHub"""
        parsed = urlparse(github_url)
        path_parts = parsed.path.strip('/').split('/')
        
        if len(path_parts) >= 2:
            owner = path_parts[0]
            repo = path_parts[1]
            return owner, repo
        return None, None
    
    def make_api_request(self, url: str) -> Dict[Any, Any]:
        """Faz requisição para API do GitHub com tratamento de rate limit"""
        try:
            response = self.session.get(url)
            
            # Verifica rate limit
            if response.status_code == 403 and 'rate limit' in response.text.lower():
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                current_time = int(time.time())
                sleep_time = max(reset_time - current_time + 1, 60)
                print(f"Rate limit atingido. Aguardando {sleep_time} segundos...")
                time.sleep(sleep_time)
                response = self.session.get(url)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Erro na requisição: {response.status_code} - {url}")
                return {}
                
        except requests.RequestException as e:
            print(f"Erro na requisição: {e}")
            return {}
    
    def get_pull_requests(self, owner: str, repo: str, state: str = 'all') -> List[Dict]:
        """Obtém pull requests do repositório"""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        params = {'state': state, 'per_page': 100}
        
        all_prs = []
        page = 1
        
        while True:
            params['page'] = page
            response = self.session.get(url, params=params)
            
            if response.status_code != 200:
                break
                
            prs = response.json()
            if not prs:
                break
                
            all_prs.extend(prs)
            page += 1
            
            # Limite para evitar muitas requisições
            if page > 10:  # Máximo 1000 PRs
                break
        
        return all_prs
    
    def check_pr_description(self, pr: Dict) -> bool:
        """Verifica se o PR contém termos relacionados a race conditions"""
        title = (pr.get('title', '') or '').lower()
        body = (pr.get('body', '') or '').lower()
        
        for term in self.pr_description_terms:
            if term.lower() in title or term.lower() in body:
                return True
        return False
    
    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Obtém arquivos modificados no PR"""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        return self.make_api_request(url)
    
    def is_test_file(self, filename: str) -> bool:
        """Verifica se o arquivo é um arquivo de teste"""
        filename_lower = filename.lower()
        
        for pattern in self.test_file_patterns:
            if pattern in filename_lower:
                return True
        return False
    
    def analyze_file_content(self, file_data: Dict) -> Dict[str, bool]:
        """Analisa o conteúdo do arquivo procurando por keywords"""
        patch = file_data.get('patch', '')
        if not patch:
            return {'has_test_keywords': False, 'has_async_keywords': False}
        
        patch_lower = patch.lower()
        
        has_test_keywords = any(keyword.lower() in patch_lower for keyword in self.test_keywords)
        has_async_keywords = any(keyword.lower() in patch_lower for keyword in self.async_keywords)
        
        return {
            'has_test_keywords': has_test_keywords,
            'has_async_keywords': has_async_keywords
        }
    
    def analyze_repository(self, repo_url: str) -> List[Dict]:
        """Analisa um repositório específico"""
        owner, repo = self.extract_repo_info(repo_url)
        if not owner or not repo:
            print(f"URL inválida: {repo_url}")
            return []
        
        print(f"Analisando {owner}/{repo}...")
        
        # Obtém pull requests
        prs = self.get_pull_requests(owner, repo)
        matching_prs = []
        
        for pr in prs:
            # Verifica se o PR tem termos relacionados a race conditions
            if not self.check_pr_description(pr):
                continue
            
            print(f"  Analisando PR #{pr['number']}: {pr['title']}")
            
            # Obtém arquivos do PR
            files = self.get_pr_files(owner, repo, pr['number'])
            if not files:
                continue
            
            # Verifica se há arquivos de teste
            test_files = [f for f in files if self.is_test_file(f.get('filename', ''))]
            if not test_files:
                continue
            
            # Analisa conteúdo dos arquivos de teste
            pr_analysis = {
                'repository': f"{owner}/{repo}",
                'pr_number': pr['number'],
                'pr_title': pr['title'],
                'pr_url': pr['html_url'],
                'pr_state': pr['state'],
                'created_at': pr['created_at'],
                'test_files': [],
                'has_matching_content': False
            }
            
            for test_file in test_files:
                file_analysis = self.analyze_file_content(test_file)
                
                file_info = {
                    'filename': test_file.get('filename', ''),
                    'status': test_file.get('status', ''),
                    'has_test_keywords': file_analysis['has_test_keywords'],
                    'has_async_keywords': file_analysis['has_async_keywords']
                }
                
                pr_analysis['test_files'].append(file_info)
                
                # Verifica se o arquivo tem ambos os tipos de keywords
                if file_analysis['has_test_keywords'] and file_analysis['has_async_keywords']:
                    pr_analysis['has_matching_content'] = True
            
            # Adiciona apenas PRs que atendem todos os critérios
            if pr_analysis['has_matching_content']:
                matching_prs.append(pr_analysis)
        
        return matching_prs
    
    def analyze_all_repositories(self, json_file: str, output_file: str = 'analysis_results.json'):
        """Analisa todos os repositórios do arquivo JSON"""
        repos = self.load_repositories(json_file)
        if not repos:
            return
        
        print(f"Analisando {len(repos)} repositórios...")
        
        all_results = []
        
        for i, repo_url in enumerate(repos, 1):
            print(f"\n[{i}/{len(repos)}] {repo_url}")
            
            try:
                results = self.analyze_repository(repo_url)
                all_results.extend(results)
                
                # Pequena pausa entre repositórios
                time.sleep(1)
                
            except Exception as e:
                print(f"Erro ao analisar {repo_url}: {e}")
                continue
        
        # Salva resultados
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*50}")
        print(f"Análise concluída!")
        print(f"Total de PRs encontrados: {len(all_results)}")
        print(f"Resultados salvos em: {output_file}")
        
        # Mostra resumo
        if all_results:
            print(f"\nResumo dos resultados:")
            for result in all_results:
                print(f"- {result['repository']} - PR #{result['pr_number']}: {result['pr_title']}")


def main():
    """Função principal"""
    # Exemplo de uso
    
    # 1. Cria arquivo JSON com repositórios (se não existir)
    repos_file = 'awesomeLists/linksGithub.json'
    
    # 2. Obtém token do GitHub (opcional mas recomendado)
    load_dotenv()
    github_token = os.getenv('GITHUB_TOKEN')
    
    # 3. Executa análise
    analyzer = GitHubPRAnalyzer(github_token)
    analyzer.analyze_all_repositories(repos_file)


if __name__ == "__main__":
    main()