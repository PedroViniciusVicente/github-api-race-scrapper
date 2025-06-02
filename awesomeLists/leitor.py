import re
import json

def extrair_links_github(arquivo_entrada, arquivo_saida):
    # Expressão regular para capturar links de repositórios GitHub
    padrao_github = r"https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"

    with open(arquivo_entrada, "r", encoding="utf-8") as f:
        conteudo = f.read()

    # Encontrar todos os links únicos
    links = re.findall(padrao_github, conteudo)
    links_unicos = sorted(set(links))  # Remove duplicatas e ordena

    # Escrever os links encontrados no arquivo de saída em formato JSON
    with open(arquivo_saida, "w", encoding="utf-8") as f:
        json.dump(links_unicos, f, indent=4, ensure_ascii=False)

    print(f"{len(links_unicos)} repositórios encontrados e salvos em '{arquivo_saida}'.")

# Exemplo de chamada
extrair_links_github("awesomeLists/texto.txt", "awesomeLists/linksGithub.json")
