import json
import csv

def extrair_dados_para_csv(arquivo_json, arquivo_csv):
    with open(arquivo_json, 'r', encoding='utf-8') as f:
        dados = json.load(f)

    campos_csv = ['repo_url', 'pr_url', 'matching_js_test_files', 'matched_terms', 'found_test_keywords', 'found_async_keywords']

    with open(arquivo_csv, 'w', newline='', encoding='utf-8') as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=campos_csv)
        writer.writeheader()

        for projeto in dados.get("matching_projects", []):
            # Extrai os dados da primeira ocorrência relevante em matching_files_details
            matching_details = projeto.get("analysis_results", {}).get("matching_files_details", [])

            if matching_details:
                detail = matching_details[0]
                linha = {
                    'repo_url': projeto.get('repo_url'),
                    'pr_url': projeto.get('pr_url'),
                    'matching_js_test_files': ';'.join(projeto.get('matching_js_test_files', [])),
                    'matched_terms': ';'.join(projeto.get('matched_terms', [])),
                    'found_test_keywords': ';'.join(detail.get('found_test_keywords', [])),
                    'found_async_keywords': ';'.join(detail.get('found_async_keywords', [])),
                }
                writer.writerow(linha)

# Exemplo de uso:
# extrair_dados_para_csv('data_repos/filtered_race_condition_prs-1.json', 'data_repos/saida1.csv')
extrair_dados_para_csv('data_repos/filtered_race_condition_prs-2.json', 'data_repos/saida2.csv')
