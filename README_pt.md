# AIGregate

MVP de um agregador de notícias de tecnologia usando IA e a API do Gemini.

Ele funciona pesquisando por notícias em feeds RSS de subreddits de programaçãp.

Para rodar, consiga a chave de API gratuita do Gemini, coloque a variável de ambiente `GEMINI_API_KEY` como sendo ela, e rode o script `scripts/create_news_summary.py` (instalando os pacotes PIP do `requirements.txt`) com o parâmetro de arquivo de saída em Markdown.

Ao invés de utilizar um servidor, se utiliza o SSG Hugo para gerar o HTML e o Github Actions para, todo dia, às 11 na noite, gerar o post.