"""
Configuracao das estacoes de monitoramento (sondas multiparametro).

Mapeamento entre arquivos do FTP (P1/P2/P3) e atributos do shapefile MODIMEDIO UMRs.
P1 esta confirmado como Belmonte pelo cabecalho TOA5 do .dat.
P2 e P3 vem com header generico ("1"); a atribuicao foi confirmada pelo
Caio (tecnico do CBH-MPS): P2 = Toyota (Resende), P3 = Principal (Paraiba do Sul).

As sondas ficam na calha do rio Paraiba do Sul e cada estacao e identificada pelo municipio.
A ETA vizinha e so referencia de localizacao: o nome dela fica apenas em site_shp, que e a
chave de juncao com o campo SITE do shapefile, e nao aparece no painel.
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
    site_shp: str  # valor do campo SITE no shapefile (ETA vizinha, so referencia de localizacao)


# Pontos extraidos do shapefile "MODIMEDIO UMRs.shp"
# Reprojetados de EPSG:31983 (UTM 23S, SIRGAS 2000) para EPSG:4326 (WGS84)
# em runtime, usando geopandas. Aqui guardamos apenas o codigo de juncao.
ESTACOES = [
    Estacao(
        codigo="P1",
        nome="Estação Volta Redonda",
        municipio="Volta Redonda",
        operadora="SAAE-VR",
        arquivo_dat="Dados_Estacao_P1.dat",
        cor="#1f77b4",
        site_shp="ETA Belmonte",
    ),
    Estacao(
        codigo="P2",
        nome="Estação Resende",
        municipio="Resende",
        operadora="Agua das Agulhas Negras",
        arquivo_dat="Dados_Estacao_P2.dat",
        cor="#d62728",
        site_shp="ETA Toyota",
    ),
    Estacao(
        codigo="P3",
        nome="Estação Paraíba do Sul",
        municipio="Paraiba do Sul",
        operadora="Aguas da Condessa",
        arquivo_dat="Dados_Estacao_P3.dat",
        cor="#2ca02c",
        site_shp="ETA Principal",
    ),
]

ESTACOES_POR_CODIGO = {e.codigo: e for e in ESTACOES}
ESTACOES_POR_NOME = {e.nome: e for e in ESTACOES}
