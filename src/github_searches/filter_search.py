import json
import requests
import time
import re
from typing import List, Dict, Tuple, Optional
import base64

class GitHubTestAnalyzer:
    def __init__(self, headers: Dict[str, str]):
        """
        Inicializa o analisador com headers do GitHub
        
        Args:
            headers: Headers para requisições HTTP incluindo Authorization token
        """
        self.headers = headers
        
        # Palavras-chave para buscar
        self.test_keywords = ["describe(", "it(", "test("]
        self.async_keywords = ["promise", "async"]
        
        # Controle de rate limiting
        self.request_count = 0
        self.start_time = time.time()
    
    def check_rate_limit(self):
        """Verifica e controla o rate limit da API do GitHub"""
        self.request_count += 1
        
        # GitHub permite 60 requests/hora sem autenticação, 5000 com token
        has_token = 'Authorization' in self.headers and 'token' in self.headers.get('Authorization', '')
        max_requests = 5000 if has_token else 60
        time_window = 3600  # 1 hora em segundos
        
        elapsed_time = time.time() - self.start_time
        
        if self.request_count >= max_requests * 0.8:  # 80% do limite
            if elapsed_time < time_window:
                sleep_time = time_window - elapsed_time + 10
                print(f"Aproximando do rate limit. Pausando por {sleep_time:.0f} segundos...")
                time.sleep(sleep_time)
                self.request_count = 0
                self.start_time = time.time()
    
    def get_file_content(self, repo_name: str, file_path: str, pr_sha: Optional[str] = None) -> Optional[str]:
        """
        Obtém o conteúdo de um arquivo do repositório
        
        Args:
            repo_name: Nome do repositório (formato: owner/repo)
            file_path: Caminho do arquivo
            pr_sha: SHA do commit do PR (opcional)
            
        Returns:
            Conteúdo do arquivo como string ou None se não encontrado
        """
        self.check_rate_limit()
        
        try:
            # URL da API para obter conteúdo do arquivo
            if pr_sha:
                url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}?ref={pr_sha}"
            else:
                url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}"
            
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                file_data = response.json()
                
                # O conteúdo vem codificado em base64
                if 'content' in file_data:
                    content = base64.b64decode(file_data['content']).decode('utf-8')
                    return content
                    
            elif response.status_code == 404:
                print(f"Arquivo não encontrado: {repo_name}/{file_path}")
                return None
            elif response.status_code == 403:
                print(f"Rate limit atingido ou acesso negado para: {repo_name}/{file_path}")
                time.sleep(60)  # Pausa de 1 minuto
                return None
            else:
                print(f"Erro {response.status_code} ao acessar: {repo_name}/{file_path}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Erro de requisição para {repo_name}/{file_path}: {e}")
            return None
        except Exception as e:
            print(f"Erro inesperado para {repo_name}/{file_path}: {e}")
            return None
    
    def get_pr_commit_sha(self, repo_name: str, pr_number: int) -> Optional[str]:
        """
        Obtém o SHA do commit de um PR
        
        Args:
            repo_name: Nome do repositório
            pr_number: Número do PR
            
        Returns:
            SHA do commit ou None se não encontrado
        """
        self.check_rate_limit()
        
        try:
            url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                pr_data = response.json()
                return pr_data['head']['sha']
            else:
                print(f"Erro ao obter PR {pr_number} do repo {repo_name}: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Erro ao obter SHA do PR {repo_name}#{pr_number}: {e}")
            return None
    
    def check_keywords_in_content(self, content: str) -> Tuple[bool, bool]:
        """
        Verifica se o conteúdo contém as palavras-chave especificadas
        
        Args:
            content: Conteúdo do arquivo
            
        Returns:
            Tuple (tem_test_keywords, tem_async_keywords)
        """
        content_lower = content.lower()
        
        # Verifica palavras-chave de teste
        has_test_keywords = any(keyword.lower() in content_lower for keyword in self.test_keywords)
        
        # Verifica palavras-chave de async
        has_async_keywords = any(keyword.lower() in content_lower for keyword in self.async_keywords)
        
        return has_test_keywords, has_async_keywords
    
    def analyze_pr(self, pr_data: Dict) -> Dict:
        """
        Analisa um PR específico
        
        Args:
            pr_data: Dados do PR do JSON
            
        Returns:
            Dicionário com resultados da análise
        """
        repo_name = pr_data['repo_name']
        pr_url = pr_data['pr_url']
        pr_number = int(pr_url.split('/')[-1])
        
        print(f"\nAnalisando PR: {pr_url}")
        
        # Obter SHA do commit do PR
        pr_sha = self.get_pr_commit_sha(repo_name, pr_number)
        
        results = {
            'repo_name': repo_name,
            'pr_url': pr_url,
            'pr_number': pr_number,
            'author': pr_data.get('author'),
            'title': pr_data.get('title'),
            'matched_terms': pr_data.get('matched_terms', []),
            'files_analyzed': [],
            'files_with_keywords': [],
            'total_files': len(pr_data.get('js_test_files', [])),
            'files_with_test_and_async': 0,
            'analysis_success': True,
            'error_message': None
        }
        
        try:
            for file_path in pr_data.get('js_test_files', []):
                print(f"  Analisando arquivo: {file_path}")
                
                file_result = {
                    'file_path': file_path,
                    'has_test_keywords': False,
                    'has_async_keywords': False,
                    'found_test_keywords': [],
                    'found_async_keywords': [],
                    'content_retrieved': False
                }
                
                # Obter conteúdo do arquivo
                content = self.get_file_content(repo_name, file_path, pr_sha)
                
                if content:
                    file_result['content_retrieved'] = True
                    
                    # Verificar palavras-chave
                    has_test, has_async = self.check_keywords_in_content(content)
                    file_result['has_test_keywords'] = has_test
                    file_result['has_async_keywords'] = has_async
                    
                    # Encontrar palavras-chave específicas encontradas
                    content_lower = content.lower()
                    file_result['found_test_keywords'] = [kw for kw in self.test_keywords if kw.lower() in content_lower]
                    file_result['found_async_keywords'] = [kw for kw in self.async_keywords if kw.lower() in content_lower]
                    
                    # Verificar se tem ambos os tipos de keywords
                    if has_test and has_async:
                        results['files_with_test_and_async'] += 1
                        file_result['matches_criteria'] = True
                        results['files_with_keywords'].append(file_result)
                        print(f"    ✓ Arquivo atende aos critérios!")
                    else:
                        file_result['matches_criteria'] = False
                        print(f"    - Test keywords: {has_test}, Async keywords: {has_async}")
                else:
                    print(f"    ✗ Não foi possível obter o conteúdo do arquivo")
                
                results['files_analyzed'].append(file_result)
                
                # Pequena pausa entre requisições
                time.sleep(0.1)
                
        except Exception as e:
            results['analysis_success'] = False
            results['error_message'] = str(e)
            print(f"Erro durante análise do PR: {e}")
        
        return results
    
    def analyze_and_save_matching_projects(self, input_json_path: str, output_json_path: str) -> Dict:
        """
        Analisa todos os PRs e salva apenas os projetos que atendem aos critérios
        
        Args:
            input_json_path: Caminho para o arquivo JSON de entrada
            output_json_path: Caminho para o arquivo JSON de saída
            
        Returns:
            Dicionário com estatísticas da análise
        """
        try:
            with open(input_json_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            pull_requests = data.get('pull_requests', [])
            print(f"Encontrados {len(pull_requests)} PRs para analisar")
            
            matching_projects = []
            analysis_stats = {
                'total_prs_analyzed': 0,
                'successful_analyses': 0,
                'prs_with_matching_files': 0,
                'total_files_analyzed': 0,
                'total_matching_files': 0,
                'errors': []
            }
            
            for i, pr_data in enumerate(pull_requests, 1):
                print(f"\n{'='*60}")
                print(f"Progresso: {i}/{len(pull_requests)}")
                
                analysis_stats['total_prs_analyzed'] += 1
                
                try:
                    pr_result = self.analyze_pr(pr_data)
                    
                    if pr_result['analysis_success']:
                        analysis_stats['successful_analyses'] += 1
                        analysis_stats['total_files_analyzed'] += pr_result['total_files']
                        analysis_stats['total_matching_files'] += pr_result['files_with_test_and_async']
                        
                        # Se o PR tem arquivos que atendem aos critérios, adiciona aos matching_projects
                        if pr_result['files_with_test_and_async'] > 0:
                            analysis_stats['prs_with_matching_files'] += 1
                            
                            # Criar estrutura do projeto que atende aos critérios
                            matching_project = {
                                'repo_url': pr_data.get('repo_url'),
                                'repo_name': pr_data['repo_name'],
                                'pr_url': pr_data['pr_url'],
                                'author': pr_data.get('author'),
                                'title': pr_data.get('title'),
                                'body': pr_data.get('body'),
                                'created_at': pr_data.get('created_at'),
                                'merged_at': pr_data.get('merged_at'),
                                'matched_terms': pr_data.get('matched_terms', []),
                                'matching_js_test_files': [f['file_path'] for f in pr_result['files_with_keywords']],
                                'analysis_results': {
                                    'total_test_files': pr_result['total_files'],
                                    'files_with_test_and_async': pr_result['files_with_test_and_async'],
                                    'matching_files_details': pr_result['files_with_keywords']
                                }
                            }
                            
                            matching_projects.append(matching_project)
                            print(f"✓ PR adicionado - {pr_result['files_with_test_and_async']} arquivo(s) correspondentes")
                        else:
                            print(f"- PR não tem arquivos que atendem aos critérios")
                    else:
                        analysis_stats['errors'].append({
                            'pr_url': pr_data.get('pr_url', 'unknown'),
                            'error': pr_result.get('error_message', 'Unknown error')
                        })
                        
                except Exception as e:
                    error_msg = f"Erro ao analisar PR {pr_data.get('pr_url', 'unknown')}: {e}"
                    print(error_msg)
                    analysis_stats['errors'].append({
                        'pr_url': pr_data.get('pr_url', 'unknown'),
                        'error': str(e)
                    })
                
                # Pausa entre PRs para evitar rate limiting
                if i % 10 == 0:
                    print("Pausa de 2 segundos...")
                    time.sleep(2)
            
            # Calcular estatísticas finais
            analysis_stats['success_rate'] = (analysis_stats['successful_analyses'] / analysis_stats['total_prs_analyzed'] * 100) if analysis_stats['total_prs_analyzed'] > 0 else 0
            analysis_stats['match_rate'] = (analysis_stats['prs_with_matching_files'] / analysis_stats['successful_analyses'] * 100) if analysis_stats['successful_analyses'] > 0 else 0
            analysis_stats['unique_repositories'] = len(set(p['repo_name'] for p in matching_projects))
            
            # Preparar dados para salvar
            output_data = {
                'metadata': {
                    'analysis_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'input_file': input_json_path,
                    'search_criteria': {
                        'test_keywords': self.test_keywords,
                        'async_keywords': self.async_keywords,
                        'requirement': 'Files must contain at least one test keyword AND one async keyword'
                    },
                    'statistics': analysis_stats
                },
                'matching_projects': matching_projects
            }
            
            # Salvar projetos correspondentes
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n{'='*80}")
            print("ANÁLISE CONCLUÍDA")
            print(f"{'='*80}")
            print(f"Projetos que atendem aos critérios salvos em: {output_json_path}")
            print(f"Total de projetos encontrados: {len(matching_projects)}")
            
            return analysis_stats
            
        except FileNotFoundError:
            print(f"Arquivo não encontrado: {input_json_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON: {e}")
            return {}
        except Exception as e:
            print(f"Erro inesperado: {e}")
            return {}
    
    def generate_summary_report(self, results: List[Dict]) -> Dict:
        """
        Gera um relatório resumido dos resultados
        
        Args:
            results: Lista de resultados da análise
            
        Returns:
            Dicionário com estatísticas resumidas
        """
        total_prs = len(results)
        successful_analyses = len([r for r in results if r.get('analysis_success', False)])
        prs_with_matching_files = len([r for r in results if r.get('files_with_test_and_async', 0) > 0])
        
        total_files_analyzed = sum(r.get('total_files', 0) for r in results)
        total_matching_files = sum(r.get('files_with_test_and_async', 0) for r in results)
        
        # Repositórios únicos
        unique_repos = set(r.get('repo_name', '') for r in results if r.get('repo_name'))
        
        # PRs com mais arquivos correspondentes
        top_prs = sorted(
            [r for r in results if r.get('files_with_test_and_async', 0) > 0],
            key=lambda x: x.get('files_with_test_and_async', 0),
            reverse=True
        )[:10]
        
        summary = {
            'total_prs_analyzed': total_prs,
            'successful_analyses': successful_analyses,
            'prs_with_matching_files': prs_with_matching_files,
            'total_files_analyzed': total_files_analyzed,
            'total_matching_files': total_matching_files,
            'unique_repositories': len(unique_repos),
            'success_rate': (successful_analyses / total_prs * 100) if total_prs > 0 else 0,
            'match_rate': (prs_with_matching_files / successful_analyses * 100) if successful_analyses > 0 else 0,
            'top_matching_prs': top_prs[:5],  # Top 5 PRs
            'repository_list': sorted(unique_repos)
        }
        
        return summary


def analyze_projects_with_criteria(headers: Dict[str, str], input_json_path: str, output_json_path: str) -> Dict:
    """
    Função principal para analisar projetos e salvar apenas os que atendem aos critérios
    
    Args:
        headers: Headers para requisições GitHub (incluindo Authorization token)
        input_json_path: Caminho para o arquivo JSON de entrada
        output_json_path: Caminho para o arquivo JSON de saída
        
    Returns:
        Dicionário com estatísticas da análise
    """
    
    # Criar analisador
    analyzer = GitHubTestAnalyzer(headers=headers)
    
    print("Iniciando análise dos arquivos de teste JavaScript...")
    print(f"Arquivo de entrada: {input_json_path}")
    print(f"Arquivo de saída: {output_json_path}")
    print(f"Procurando por arquivos que contenham:")
    print(f"- Palavras-chave de teste: {analyzer.test_keywords}")
    print(f"- Palavras-chave async: {analyzer.async_keywords}")
    
    # Verificar se tem token de autenticação
    has_token = 'Authorization' in headers and 'token' in headers.get('Authorization', '')
    if not has_token:
        print("\n⚠️  AVISO: Executando sem token do GitHub. Rate limit será mais restritivo (60 req/hora)")
    else:
        print(f"\n✓ Executando com token de autenticação do GitHub")
    
    # Executar análise e salvar resultados
    stats = analyzer.analyze_and_save_matching_projects(input_json_path, output_json_path)
    
    if stats:
        print(f"\n{'='*80}")
        print("ESTATÍSTICAS FINAIS")
        print(f"{'='*80}")
        print(f"Total de PRs analisados: {stats['total_prs_analyzed']}")
        print(f"Análises bem-sucedidas: {stats['successful_analyses']}")
        print(f"PRs com arquivos correspondentes: {stats['prs_with_matching_files']}")
        print(f"Total de arquivos analisados: {stats['total_files_analyzed']}")
        print(f"Arquivos que atendem aos critérios: {stats['total_matching_files']}")
        print(f"Repositórios únicos encontrados: {stats['unique_repositories']}")
        print(f"Taxa de sucesso: {stats['success_rate']:.1f}%")
        print(f"Taxa de correspondência: {stats['match_rate']:.1f}%")
        
        if stats['errors']:
            print(f"\nErros encontrados: {len(stats['errors'])}")
            for error in stats['errors'][:5]:  # Mostrar apenas os primeiros 5 erros
                print(f"  - {error['pr_url']}: {error['error']}")
    
    return stats


def main():
    """Função de exemplo para executar a análise"""
    
    # Exemplo de configuração
    token = "YOUR_GITHUB_TOKEN_HERE"  # Substitua pelo seu token
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}"
    }
    
    input_file = "input_data.json"  # Arquivo JSON de entrada
    output_file = "matching_projects.json"  # Arquivo JSON de saída
    
    # Executar análise
    stats = analyze_projects_with_criteria(headers, input_file, output_file)
    
    return stats


if __name__ == "__main__":
    main()