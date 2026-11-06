import csv
import io
import re
from pathlib import Path

import numpy as np
import pandas as pd

PASTA = Path(__file__).parent
PASTA_BRUTOS = PASTA / "dados_brutos"
PASTA_TRATADOS = PASTA / "dados_tratados"


UFS = {
    11: ("RO", "Norte"), 12: ("AC", "Norte"), 13: ("AM", "Norte"), 14: ("RR", "Norte"),
    15: ("PA", "Norte"), 16: ("AP", "Norte"), 17: ("TO", "Norte"),
    21: ("MA", "Nordeste"), 22: ("PI", "Nordeste"), 23: ("CE", "Nordeste"),
    24: ("RN", "Nordeste"), 25: ("PB", "Nordeste"), 26: ("PE", "Nordeste"),
    27: ("AL", "Nordeste"), 28: ("SE", "Nordeste"), 29: ("BA", "Nordeste"),
    31: ("MG", "Sudeste"), 32: ("ES", "Sudeste"), 33: ("RJ", "Sudeste"), 35: ("SP", "Sudeste"),
    41: ("PR", "Sul"), 42: ("SC", "Sul"), 43: ("RS", "Sul"),
    50: ("MS", "Centro-Oeste"), 51: ("MT", "Centro-Oeste"), 52: ("GO", "Centro-Oeste"),
    53: ("DF", "Centro-Oeste"),
}


SIMBOLOS_SEM_VALOR = {"-", "..", "...", "X", ""}

COLUNAS = ["tabela", "nivel", "cod", "territorio", "sigla_uf", "regiao",
           "tipo_recorte", "recorte", "ano", "sexo", "horas"]


def _para_numero(valor: str) -> float:
    valor = valor.strip()
    if valor in SIMBOLOS_SEM_VALOR:
        return np.nan
    return float(valor.replace(".", "").replace(",", "."))


def _ler_texto(arquivo) -> str:
    if isinstance(arquivo, (str, Path)):
        dados = Path(arquivo).read_bytes()
    else:
        dados = arquivo.getvalue() if hasattr(arquivo, "getvalue") else arquivo.read()
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise ValueError("Não foi possível ler o arquivo (codificação desconhecida).")


def ler_tabela_sidra(arquivo) -> pd.DataFrame:
    texto = _ler_texto(arquivo)
    linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))


    achado = re.search(r"Tabela\s+(\d+)", linhas[0][0]) if linhas and linhas[0] else None
    numero_tabela = int(achado.group(1)) if achado else None

    idx_sexo = next(i for i, l in enumerate(linhas)
                    if any(c.strip() in ("Homens", "Mulheres") for c in l))
    linha_anos, linha_sexo = linhas[idx_sexo - 1], linhas[idx_sexo]

    n_dim = 0
    while n_dim < len(linha_sexo) and linha_sexo[n_dim] == linha_anos[n_dim]:
        n_dim += 1
    nomes_dim = linha_sexo[:n_dim]
    tem_recorte = n_dim == 4  


    anos, ultimo = [], None
    for i in range(n_dim, len(linha_sexo)):
        c = linha_anos[i] if i < len(linha_anos) else ""
        ultimo = int(c) if c.strip() else ultimo
        anos.append(ultimo)
    sexos = [s.strip() for s in linha_sexo[n_dim:]]

    registros = []
    for linha in linhas[idx_sexo + 1:]:
        if not linha or linha[0].strip() not in ("BR", "GR", "UF"):
            if linha and linha[0].startswith("Fonte"):
                break
            continue
        nivel, cod, territorio = linha[0].strip(), int(linha[1]), linha[2].strip()
        sigla, regiao = UFS.get(cod, ("BR", "Brasil")) if nivel == "UF" else ("BR", "Brasil")
        tipo_recorte = nomes_dim[3] if tem_recorte else "Total"
        recorte = linha[3].strip() if tem_recorte else "Total"
        for ano, sexo, valor in zip(anos, sexos, linha[n_dim:]):
            registros.append([numero_tabela, nivel, cod, territorio, sigla, regiao,
                              tipo_recorte, recorte, ano, sexo, _para_numero(valor)])

    df = pd.DataFrame(registros, columns=COLUNAS)
    return df.dropna(subset=["horas"]).reset_index(drop=True)


def carregar(arquivo) -> pd.DataFrame:
    nome = getattr(arquivo, "name", str(arquivo)).lower()
    if nome.endswith((".xlsx", ".xls")):
        df = pd.read_excel(arquivo)
    else:
        texto = _ler_texto(arquivo)
        if texto.lstrip().startswith('"Tabela') or texto.lstrip().startswith("Tabela"):
            return ler_tabela_sidra(arquivo)
        df = pd.read_csv(io.StringIO(texto), sep=None, engine="python")
    faltando = set(COLUNAS) - set(df.columns)
    if faltando:
        raise ValueError(f"Arquivo fora do padrão. Colunas faltando: {sorted(faltando)}")
    df["horas"] = pd.to_numeric(df["horas"], errors="coerce")
    return df.dropna(subset=["horas"])[COLUNAS]


def main():
    PASTA_TRATADOS.mkdir(exist_ok=True)
    todas = []
    for caminho in sorted(PASTA_BRUTOS.glob("*.csv")):
        df = ler_tabela_sidra(caminho)
        saida = PASTA_TRATADOS / f"{caminho.stem}_tratada.csv"
        df.to_csv(saida, index=False, encoding="utf-8-sig")
        df.to_excel(saida.with_suffix(".xlsx"), index=False)
        print(f"{caminho.name}: {len(df)} linhas -> {saida.name} (+ .xlsx)")
        todas.append(df)
    base = pd.concat(todas, ignore_index=True)
    base.to_csv(PASTA_TRATADOS / "base_afazeres_completa.csv", index=False, encoding="utf-8-sig")
    print(f"Base completa: {len(base)} linhas -> base_afazeres_completa.csv")


if __name__ == "__main__":
    main()
