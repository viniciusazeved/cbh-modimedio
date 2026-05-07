"""
Configuracao das estacoes de monitoramento (sondas multiparametro).

Mapeamento entre arquivos do FTP (P1/P2/P3) e atributos do shapefile MODIMEDIO UMRs.
P1 esta confirmado como Belmonte pelo cabecalho TOA5 do .dat.
P2 e P3 estao com header generico ("1") - mapeamento abaixo eh provisorio
e pode ser ajustado se a equipe SIGA confirmar a ordem real.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Estacao:
    codigo: str
    nome: str
    municipio: str
    operadora: str
    arquivo_dat: str
    cor: str  # cor primaria nos graficos / mapa


# Pontos extraidos do shapefile "MODIMEDIO UMRs.shp"
# Reprojetados de EPSG:31983 (UTM 23S, SIRGAS 2000) para EPSG:4326 (WGS84)
# em runtime, usando geopandas. Aqui guardamos apenas o codigo de juncao.
ESTACOES = [
    Estacao(
        codigo="P1",
        nome="ETA Belmonte",
        municipio="Volta Redonda",
        operadora="SAAE-VR",
        arquivo_dat="Dados_Estacao_P1.dat",
        cor="#1f77b4",
    ),
    Estacao(
        codigo="P2",
        nome="ETA Principal",
        municipio="Paraiba do Sul",
        operadora="Aguas da Condessa",
        arquivo_dat="Dados_Estacao_P2.dat",
        cor="#2ca02c",
    ),
    Estacao(
        codigo="P3",
        nome="ETA Toyota",
        municipio="Resende",
        operadora="Agua das Agulhas Negras",
        arquivo_dat="Dados_Estacao_P3.dat",
        cor="#d62728",
    ),
]

ESTACOES_POR_CODIGO = {e.codigo: e for e in ESTACOES}
ESTACOES_POR_NOME = {e.nome: e for e in ESTACOES}
