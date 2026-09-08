# Minerador Estático de Suítes de Teste Python

Ferramenta de mineração de repositórios desenvolvida para extração de métricas de qualidade de software em projetos Python que utilizam `pytest`. O script realiza análises estáticas sem a necessidade de instanciar os ambientes virtuais dos repositórios alvo.

## Funcionalidades
- Clonagem temporária automática de repositórios via GitHub.
- Cálculo rigoroso de SLOC (Source Lines of Code) utilizando `cloc`, separando código de produção e testes.
- Contagem estrutural de funções de teste (`test_`) e fixtures customizadas utilizando a Árvore Sintática Abstrata (AST).
- Exportação automatizada dos dados para `.csv`.

## Tecnologias e Ferramentas
- Python 3.x
- [cloc](https://github.com/AlDanial/cloc) (Count Lines of Code)
- Bibliotecas: `ast`, `requests`, `subprocess`, `csv`

## Como executar
1. Instale o utilitário `cloc` no seu sistema:
   ```bash
   sudo apt install cloc  # Debian/Ubuntu/Mint
   sudo dnf install cloc  # Fedora

2. Crie e ative o ambiente virtual:
    python -m venv venv
    source venv/bin/activate

3. Instale as dependências:
    pip install requests

4. Crie um arquivo candidatos.txt (ou adicione mais projetos a este arquivo) na raiz do projeto com as URLs dos repositórios do GitHub (uma por linha) e execute o minerador.
    python analisador.py
