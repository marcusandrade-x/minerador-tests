"""
Minerador estático de suítes de teste em repositórios Python do GitHub.

Script de apoio à Iniciação Científica: para cada URL de repositório listada
em `candidatos.txt`, clona o projeto temporariamente, separa código de
produção de código de teste, mede LOC via `cloc`, e conta funções de teste
e fixtures customizadas via AST.
"""

import ast
import csv
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DIRETORIO_REPOS = Path("./repositorios_temp")
ARQUIVO_URLS = Path("candidatos.txt")
ARQUIVO_CSV = Path("resultados_projetos.csv")
CABECALHO_CSV = [
    "project_name", "descricao", "url", "num_tests", "num_fixtures",
    "loc_tests", "arquivos_tests", "loc_producao", "arquivos_producao",
    "loc_projeto_total",
]


@dataclass
class MetricasRepo:
    """Consolida as métricas estáticas extraídas de um repositório."""
    qtd_arquivos_teste: int
    loc_testes: int
    qtd_arquivos_producao: int
    loc_producao: int
    total_testes: int
    total_fixtures: int

    @property
    def loc_projeto_total(self) -> int:
        return self.loc_testes + self.loc_producao

    def as_row(self, nome_repo: str, descricao: str, url_repo: str) -> list:
        """Monta a linha do CSV na mesma ordem de CABECALHO_CSV."""
        return [
            nome_repo, descricao, url_repo,
            self.total_testes, self.total_fixtures,
            self.loc_testes, self.qtd_arquivos_teste,
            self.loc_producao, self.qtd_arquivos_producao,
            self.loc_projeto_total,
        ]


def coletar_metadados_github(dono_repo: str, nome_repo: str) -> str:
    """Busca a descrição do projeto na API do GitHub usando token de variável de ambiente."""
    url_api = f"https://api.github.com/repos/{dono_repo}/{nome_repo}"
    github_token = os.environ.get("GITHUB_TOKEN")

    headers = {"User-Agent": "Script-Analise-IC-Python"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    try:
        resposta = requests.get(url_api, headers=headers, timeout=10)
        if resposta.status_code == 200:
            return resposta.json().get("description") or "Sem descrição"
        elif resposta.status_code == 403:
            logger.warning(f"Limite da API (403) para {nome_repo}. Configure o GITHUB_TOKEN.")
        else:
            logger.warning(f"GitHub API retornou {resposta.status_code} para {nome_repo}.")
    except requests.RequestException as e:
        logger.warning(f"Falha ao buscar metadados de {nome_repo}: {e}")

    return "Sem descrição"


def rodar_cloc(lista_arquivos: list[Path]) -> tuple[int, int]:
    """Chama o cloc no terminal passando uma lista de arquivos e retorna (num_arquivos, loc)."""
    if not lista_arquivos:
        return 0, 0

    caminhos = [str(arq) for arq in lista_arquivos]
    comando = ["cloc", "--json"] + caminhos

    resultado = subprocess.run(comando, capture_output=True, text=True)

    try:
        dados = json.loads(resultado.stdout)
        if "Python" in dados:
            return dados["Python"]["nFiles"], dados["Python"]["code"]
    except json.JSONDecodeError:
        logger.warning("Não foi possível interpretar a saída do cloc.")

    return 0, 0


def classificar_arquivos(caminho_repo: Path) -> tuple[list[Path], list[Path]]:
    """Lista os .py do repositório e separa arquivos de teste dos de produção."""
    todos_py = [
        f for f in caminho_repo.rglob("*.py")
        if not any(parte.startswith(".") for parte in f.parts)
    ]

    arquivos_teste = [
        f for f in todos_py
        if f.name.startswith("test_") or f.name.endswith("_test.py") or f.name == "conftest.py"
    ]
    arquivos_producao = [f for f in todos_py if f not in arquivos_teste]

    return arquivos_teste, arquivos_producao


def contar_fixtures(arquivos: list[Path]) -> int:
    """Conta funções decoradas com fixture do pytest via AST (ignora comentários e strings).

    Cobre tanto `@pytest.fixture` / `@pytest.fixture(...)` (ast.Attribute) quanto
    `@fixture` / `@fixture(...)` (ast.Name), caso do `from pytest import fixture`.
    Nota: a checagem do `ast.Name` é uma heurística por nome (não resolve a origem
    do import), então um decorator local chamado `fixture` sem relação com o pytest
    geraria um falso positivo raro.
    """
    total = 0
    for arquivo in arquivos:
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, SyntaxError):
            continue

        for no in ast.walk(arvore):
            if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in no.decorator_list:
                alvo = decorator.func if isinstance(decorator, ast.Call) else decorator
                eh_atributo = isinstance(alvo, ast.Attribute) and alvo.attr == "fixture"
                eh_nome = isinstance(alvo, ast.Name) and alvo.id == "fixture"
                if eh_atributo or eh_nome:
                    total += 1
                    break
    return total


def contar_funcoes_teste(arquivos_teste: list[Path]) -> int:
    """Conta funções de teste (test_*) via AST nos arquivos de teste."""
    total = 0
    for arquivo in arquivos_teste:
        try:
            codigo_fonte = arquivo.read_text(encoding="utf-8")
            arvore = ast.parse(codigo_fonte)
            for no in ast.walk(arvore):
                if isinstance(no, ast.FunctionDef) and no.name.startswith("test_"):
                    total += 1
        except (UnicodeDecodeError, SyntaxError):
            continue
    return total


def contar_metricas_estaticas_testes(caminho_repo: Path) -> MetricasRepo:
    """Orquestra a extração de todas as métricas estáticas de um repositório clonado."""
    arquivos_teste, arquivos_producao = classificar_arquivos(caminho_repo)
    todos_py = arquivos_teste + arquivos_producao

    qtd_arquivos_teste, loc_testes = rodar_cloc(arquivos_teste)
    qtd_arquivos_producao, loc_producao = rodar_cloc(arquivos_producao)

    total_fixtures = contar_fixtures(todos_py)
    total_testes = contar_funcoes_teste(arquivos_teste)

    return MetricasRepo(
        qtd_arquivos_teste=qtd_arquivos_teste,
        loc_testes=loc_testes,
        qtd_arquivos_producao=qtd_arquivos_producao,
        loc_producao=loc_producao,
        total_testes=total_testes,
        total_fixtures=total_fixtures,
    )


def analisar_candidato(url_repo: str, diretorio_base: Path) -> list:
    """Clona, analisa e limpa um único repositório candidato, retornando a linha do CSV."""
    partes = url_repo.rstrip("/").split("/")
    dono_repo, nome_repo = partes[-2], partes[-1]

    descricao = coletar_metadados_github(dono_repo, nome_repo)
    caminho_repo = diretorio_base / nome_repo

    if not caminho_repo.exists():
        subprocess.run(
            ["git", "clone", "--depth", "1", url_repo, str(caminho_repo)],
            capture_output=True,
        )

    metricas = contar_metricas_estaticas_testes(caminho_repo)
    return metricas.as_row(nome_repo, descricao, url_repo)


def carregar_urls_processadas(arquivo_csv: Path) -> set[str]:
    """Lê o CSV existente (se houver) e retorna o conjunto de URLs já processadas."""
    urls_processadas = set()
    if not arquivo_csv.exists():
        return urls_processadas

    with open(arquivo_csv, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # pula cabeçalho
        for linha in reader:
            if len(linha) >= 3:
                urls_processadas.add(linha[2])

    return urls_processadas


def limpar_clone(diretorio_base: Path, url_repo: str) -> None:
    """Remove o diretório clonado de um repositório, ignorando erros."""
    nome_repo = url_repo.rstrip("/").split("/")[-1]
    caminho_repo = diretorio_base / nome_repo
    if caminho_repo.exists():
        shutil.rmtree(caminho_repo, ignore_errors=True)


def main() -> None:
    DIRETORIO_REPOS.mkdir(exist_ok=True)

    if not ARQUIVO_URLS.exists():
        logger.error("Crie um arquivo 'candidatos.txt' com as URLs dos repositórios.")
        return

    urls_candidatos = [
        linha.strip() for linha in ARQUIVO_URLS.read_text().splitlines() if linha.strip()
    ]

    urls_ja_processadas = carregar_urls_processadas(ARQUIVO_CSV)
    novos_para_processar = [url for url in urls_candidatos if url not in urls_ja_processadas]

    if not novos_para_processar:
        logger.info("Nenhum repositório novo para analisar. Saindo...")
        return

    modo_abertura = "a" if ARQUIVO_CSV.exists() else "w"

    with open(ARQUIVO_CSV, modo_abertura, newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if modo_abertura == "w":
            writer.writerow(CABECALHO_CSV)

        for url in novos_para_processar:
            logger.info(f"Analisando {url}...")
            try:
                dados = analisar_candidato(url, DIRETORIO_REPOS)
                writer.writerow(dados)
                f.flush()
            except Exception as e:
                logger.error(f"Erro ao analisar {url}: {e}")
            finally:
                limpar_clone(DIRETORIO_REPOS, url)

    logger.info("Análise concluída!")


if __name__ == "__main__":
    main()