import numpy as np
import pandas as pd


def resumo_estatistico(valores, ddof: int = 0) -> dict:
    s = pd.Series(valores, dtype="float64").dropna()
    if s.empty:
        return {}

    q1, q2, q3 = s.quantile([0.25, 0.50, 0.75])
    iqr = q3 - q1
    lim_inf, lim_sup = q1 - 1.5 * iqr, q3 + 1.5 * iqr

    contagem = s.value_counts()
    if contagem.max() == 1:
        moda = "Amodal (nenhum valor se repete)"
    else:
        moda = sorted(contagem[contagem == contagem.max()].index.tolist())

    variancia = s.var(ddof=ddof)
    return {
        "n": int(s.count()),
        "media": s.mean(),
        "mediana": q2,
        "moda": moda,
        "minimo": s.min(),
        "maximo": s.max(),
        "amplitude": s.max() - s.min(),
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "iqr": iqr,
        "variancia": variancia,
        "desvio_padrao": np.sqrt(variancia),
        "limite_inferior": lim_inf,
        "limite_superior": lim_sup,
    }


def outliers(df: pd.DataFrame, coluna: str = "horas") -> pd.DataFrame:
    r = resumo_estatistico(df[coluna])
    if not r:
        return df.iloc[0:0]
    fora = (df[coluna] < r["limite_inferior"]) | (df[coluna] > r["limite_superior"])
    return df[fora]


def tabela_resumo(r: dict) -> pd.DataFrame:
    nomes = {
        "n": "Nº de observações", "media": "Média", "mediana": "Mediana", "moda": "Moda",
        "minimo": "Mínimo", "maximo": "Máximo", "amplitude": "Amplitude",
        "q1": "Q1 (25%)", "q2": "Q2 (50%)", "q3": "Q3 (75%)", "iqr": "IQR (Q3 − Q1)",
        "variancia": "Variância", "desvio_padrao": "Desvio padrão",
        "limite_inferior": "Limite inferior (Q1 − 1,5·IQR)",
        "limite_superior": "Limite superior (Q3 + 1,5·IQR)",
    }
    linhas = []
    for chave, rotulo in nomes.items():
        v = r.get(chave)
        if isinstance(v, (float, np.floating)):
            v = f"{v:.2f}".replace(".", ",")
        elif isinstance(v, list):
            v = "; ".join(f"{x:.1f}".replace(".", ",") for x in v)
        linhas.append({"Medida": rotulo, "Valor": str(v)})
    return pd.DataFrame(linhas)
