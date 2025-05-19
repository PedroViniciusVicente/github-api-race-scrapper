# GITHUB-API-SCRAPER
Ferramenta que utiliza a API do GitHub para auxiliar na procura por Event Races em projetos open-source JavaScript com base nas palavras chave presentes de issues fechadas em seus repositorios. 

## Passo a passo da instalação e execução do GITHUB-API-SCRAPER

### Ambiente Virtual
Criação do ambiente virtual para fazer instalações locais e não globais:
```
python3 -m venv venv
```

Ativar o ambiente virtual
```
source venv/bin/activate
```


### Instalação das Bibliotecas
Instalar as libs necessárias usando o pip
```
pip install requests
pip install python-dotenv
```

Ou simplesmente
```
pip install -r requirements.txt
```
<!-- Mas para isso eu preciso ter feito o "pip freeze > requirements.txt" para salvar -->


### Token do GitHub
Criar o arquivo .env
```
touch .env
```

Adicionar nesse arquivo o token de acesso pessoal no seguinte formato:
```
GITHUB_TOKEN=seu_token
```
O token pode ser gerado em: https://github.com/settings/tokens

### Executar a aplicação
Executar a aplicação
```
python3 main.py 
```

<!-- Problemas com o erro 403? Então verifique quantas requisições ainda restam pelo seu token e em quanto tempo ele volta
curl -H "Authorization: token SEU_TOKEN" https://api.github.com/rate_limit -->
