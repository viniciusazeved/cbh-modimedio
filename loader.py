"""
Camada de carregamento integrada para o painel.
Orquestra FTP -> parse -> dataframe consolidado, com cache do Streamlit.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st

import ftp_client
import limites
from parser import ler_toa5, metadados_toa5
from stations import ESTACOES, Estacao


SHP_PATH = Path("SHP/MODIMEDIO UMRs.shp")
SHP_RH3_PATH = Path("SHP/RH_III.shp")


@st.cache_data(ttl=300, show_spinner=False)
def carregar_dados_estacoes(_ttl_token: int = 0) -> tuple[pd.DataFrame, dict[str, dict]]:
    """
    Baixa (com cache) os 3 .dat do FTP e devolve:
      - df_long: dataframe longo com colunas [estacao, codigo, TIMESTAMP, parametro, valor]
      - metadados: dict[codigo] -> metadados TOA5
    """
    arquivos = [e.arquivo_dat for e in ESTACOES]
    paths = ftp_client.baixar_todas(arquivos, force=bool(_ttl_token))

    frames = []
    metadados = {}
    for est in ESTACOES:
        p = paths[est.arquivo_dat]
        meta = metadados_toa5(p)
        df = ler_toa5(p)
        # Mascara valores fisicamente implausiveis (zeros literais, fora de faixa)
        df = limites.mascarar_implausiveis(df)
        df["estacao"] = est.nome
        df["codigo"] = est.codigo
        df["municipio"] = est.municipio
        df["operadora"] = est.operadora
        frames.append(df)
        metadados[est.codigo] = meta

    df_full = pd.concat(frames, ignore_index=True)
    return df_full, metadados


def diagnostico_operacional(df_full: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada (estacao, parametro), retorna o intervalo real de leituras validas
    apos mascaramento. Util para entender lacunas e calibracoes problematicas.
    """
    rows = []
    chaves_relev = ["pH", "OD", "Turb", "Temp", "Cond", "ORP"]
    for est in ESTACOES:
        sub = df_full[df_full["codigo"] == est.codigo]
        for chave in chaves_relev:
            if chave not in sub.columns:
                continue
            valid = sub.dropna(subset=[chave])
            n = len(valid)
            if n == 0:
                rows.append({
                    "Estacao": est.nome,
                    "Parametro": chave,
                    "n_validos": 0,
                    "Inicio": None,
                    "Fim": None,
                    "Cobertura_pct": 0.0,
                })
            else:
                total = len(sub)
                rows.append({
                    "Estacao": est.nome,
                    "Parametro": chave,
                    "n_validos": int(n),
                    "Inicio": valid["TIMESTAMP"].min(),
                    "Fim": valid["TIMESTAMP"].max(),
                    "Cobertura_pct": round(100 * n / total, 1) if total else 0.0,
                })
    return pd.DataFrame(rows)


def forcar_atualizacao() -> None:
    """Limpa caches do streamlit e baixa de novo."""
    carregar_dados_estacoes.clear()


@st.cache_data(show_spinner=False)
def carregar_pontos_geograficos() -> gpd.GeoDataFrame:
    """Carrega o shapefile e reprojeta para WGS84."""
    gdf = gpd.read_file(SHP_PATH)
    gdf = gdf.to_crs(epsg=4326)
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y
    return gdf


@st.cache_data(show_spinner=False)
def carregar_limite_rh3() -> gpd.GeoDataFrame | None:
    """Carrega o poligono da RH3 (Medio Paraiba do Sul) reprojetado para WGS84."""
    if not SHP_RH3_PATH.exists():
        return None
    gdf = gpd.read_file(SHP_RH3_PATH)
    return gdf.to_crs(epsg=4326)


def pontos_com_estacoes() -> pd.DataFrame:
    """Junta o shapefile com a config de estacoes pelo nome (campo SITE)."""
    gdf = carregar_pontos_geograficos()
    df_est = pd.DataFrame([
        {
            "codigo": e.codigo,
            "nome": e.nome,
            "municipio_cfg": e.municipio,
            "operadora_cfg": e.operadora,
            "cor": e.cor,
        }
        for e in ESTACOES
    ])
    out = df_est.merge(gdf[["SITE", "Municipio", "Concession", "lon", "lat"]],
                       left_on="nome", right_on="SITE", how="left")
    return out


def ultima_leitura_por_estacao(df: pd.DataFrame, parametro: str) -> pd.DataFrame:
    """Para cada estacao, retorna ultima leitura valida (nao-NaN) do parametro."""
    if parametro not in df.columns:
        return pd.DataFrame()
    sub = df.dropna(subset=[parametro])
    if sub.empty:
        return pd.DataFrame()
    idx = sub.groupby("codigo")["TIMESTAMP"].idxmax()
    return sub.loc[idx, ["codigo", "estacao", "TIMESTAMP", parametro]].reset_index(drop=True)
