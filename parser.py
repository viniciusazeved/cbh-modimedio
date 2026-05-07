"""
Parser para arquivos TOA5 (Campbell Scientific datalogger CR300).

Formato:
- Linha 1: cabecalho ("TOA5", nome_estacao, modelo, ...)
- Linha 2: nomes dos campos
- Linha 3: unidades
- Linha 4: tipo de processamento (Smp, Tot, Avg, ...)
- Linhas 5+: dados (valores "NAN" para sensor sem leitura)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def ler_toa5(caminho: str | Path) -> pd.DataFrame:
    """Le um arquivo .dat TOA5 e devolve DataFrame com colunas tipadas."""
    caminho = Path(caminho)

    # Linha 2 do TOA5 contem os nomes (header=1, com skiprows da linha 0).
    # As linhas 3 e 4 sao unidades e tipos - puladas.
    df = pd.read_csv(
        caminho,
        skiprows=[0, 2, 3],
        header=0,
        encoding="latin-1",
        na_values=["NAN", "NaN", "nan", ""],
        low_memory=False,
    )

    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], errors="coerce")
    df = df.dropna(subset=["TIMESTAMP"]).reset_index(drop=True)

    # tudo virara numerico exceto TIMESTAMP
    for col in df.columns:
        if col == "TIMESTAMP":
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("TIMESTAMP").reset_index(drop=True)
    return df


def metadados_toa5(caminho: str | Path) -> dict:
    """Le apenas as 4 primeiras linhas e devolve metadados (nome, modelo, unidades, tipos)."""
    caminho = Path(caminho)
    with open(caminho, "r", encoding="latin-1") as f:
        cab = next(f).strip().replace('"', "").split(",")
        campos = next(f).strip().replace('"', "").split(",")
        unidades = next(f).strip().replace('"', "").split(",")
        tipos = next(f).strip().replace('"', "").split(",")
    return {
        "formato": cab[0] if cab else "",
        "nome_estacao": cab[1] if len(cab) > 1 else "",
        "modelo": cab[2] if len(cab) > 2 else "",
        "serial": cab[3] if len(cab) > 3 else "",
        "programa": cab[5] if len(cab) > 5 else "",
        "tabela": cab[7] if len(cab) > 7 else "",
        "campos": campos,
        "unidades": dict(zip(campos, unidades)),
        "tipos": dict(zip(campos, tipos)),
    }
