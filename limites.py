"""
Limites para aguas doces de Classe II - Resolucao CONAMA 357/2005, Art. 15.

Apenas parametros monitorados pelas sondas multiparametro estao listados.
Parametros sem limite explicito na CONAMA (Cond, ORP, Temp, etc.) sao
exibidos como informativos.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Parametro:
    chave: str           # nome da coluna no .dat
    rotulo: str          # nome amigavel para exibicao
    unidade: str
    limite_min: float | None    # CONAMA 357/2005 Classe II (None = sem limite)
    limite_max: float | None
    descricao: str
    cor_grafico: str = "#1f77b4"
    # Faixa de plausibilidade fisica - valores fora indicam erro de
    # calibracao ou sonda enviando lixo (sao mascarados como NaN no painel).
    plausivel_min: float | None = None
    plausivel_max: float | None = None
    # Se True, valor 0 literal eh tratado como "sem leitura" (sonda apagada).
    zero_invalido: bool = False


PARAMETROS = [
    Parametro(
        chave="pH",
        rotulo="pH",
        unidade="",
        limite_min=6.0,
        limite_max=9.0,
        descricao="Potencial hidrogenionico. CONAMA 357: 6,0 - 9,0.",
        cor_grafico="#9467bd",
        plausivel_min=4.0,
        plausivel_max=11.0,
        zero_invalido=True,
    ),
    Parametro(
        chave="OD",
        rotulo="Oxigenio Dissolvido",
        unidade="mg/L",
        limite_min=5.0,
        limite_max=None,
        descricao="OD nao inferior a 5 mg/L em qualquer amostra (CONAMA 357 Classe II).",
        cor_grafico="#1f77b4",
        plausivel_min=0.0,
        plausivel_max=14.0,  # saturacao max em agua doce ~ 10-12 mg/L; >14 indica calibracao errada
        zero_invalido=True,
    ),
    Parametro(
        chave="Turb",
        rotulo="Turbidez",
        unidade="NTU",
        limite_min=None,
        limite_max=100.0,
        descricao="Limite ate 100 UNT para Classe II (CONAMA 357).",
        cor_grafico="#8c564b",
        plausivel_min=0.0,
        plausivel_max=4000.0,  # limite tipico de leitura de sonda
        zero_invalido=False,
    ),
    Parametro(
        chave="Temp",
        rotulo="Temperatura da agua",
        unidade="C",
        limite_min=None,
        limite_max=None,
        descricao="Sem limite numerico fixo na CONAMA 357 (apenas variacao em zona de mistura).",
        cor_grafico="#d62728",
        plausivel_min=0.0,
        plausivel_max=50.0,
        zero_invalido=True,
    ),
    Parametro(
        chave="Cond",
        rotulo="Condutividade Eletrica",
        unidade="uS/cm",
        limite_min=None,
        limite_max=None,
        descricao="Sem limite na CONAMA 357. Indicativo de solidos dissolvidos.",
        cor_grafico="#17becf",
        plausivel_min=0.0,
        plausivel_max=2000.0,
        zero_invalido=True,
    ),
    Parametro(
        chave="ORP",
        rotulo="Potencial Redox",
        unidade="mV",
        limite_min=None,
        limite_max=None,
        descricao="Sem limite na CONAMA 357. Indicador de condicoes oxi-redutoras.",
        cor_grafico="#7f7f7f",
        plausivel_min=-1000.0,
        plausivel_max=1000.0,
        zero_invalido=False,
    ),
    Parametro(
        chave="Prof",
        rotulo="Profundidade da sonda",
        unidade="m",
        limite_min=None,
        limite_max=None,
        descricao="Profundidade medida pela sonda (nivel de imersao).",
        cor_grafico="#2ca02c",
    ),
    Parametro(
        chave="ChuvaTotal",
        rotulo="Chuva acumulada",
        unidade="mm",
        limite_min=None,
        limite_max=None,
        descricao="Pluviosidade acumulada no intervalo de amostragem.",
        cor_grafico="#1f77b4",
    ),
    Parametro(
        chave="TempExt",
        rotulo="Temperatura externa (ar)",
        unidade="C",
        limite_min=None,
        limite_max=None,
        descricao="Temperatura do ar registrada pelo sensor externo.",
        cor_grafico="#ff7f0e",
    ),
    Parametro(
        chave="UmidadeRelativa",
        rotulo="Umidade relativa do ar",
        unidade="%",
        limite_min=None,
        limite_max=None,
        descricao="Umidade relativa do ar (variavel meteorologica).",
        cor_grafico="#bcbd22",
    ),
    Parametro(
        chave="Alimentacao",
        rotulo="Alimentacao da estacao",
        unidade="V",
        limite_min=11.0,
        limite_max=15.0,
        descricao="Tensao de alimentacao do datalogger - faixa operacional saudavel: 12-14 V.",
        cor_grafico="#7f7f7f",
    ),
]

PARAMS_POR_CHAVE = {p.chave: p for p in PARAMETROS}

# Parametros considerados "qualitativos da agua" (sao os que entram nas paginas principais)
PARAMS_QUALIDADE = ["pH", "OD", "Turb", "Temp", "Cond", "ORP"]

# Parametros "auxiliares" (meteorologicos / operacionais)
PARAMS_AUX = ["ChuvaTotal", "TempExt", "UmidadeRelativa", "Prof", "Alimentacao"]


def status_classe_ii(chave: str, valor: float) -> str:
    """Retorna 'conforme', 'nao conforme', 'suspeito', 'sem dado' ou 'sem limite'."""
    if valor is None or (isinstance(valor, float) and (valor != valor)):  # NaN
        return "sem dado"
    p = PARAMS_POR_CHAVE.get(chave)
    if p is None:
        return "sem limite"
    if not valor_plausivel(chave, valor):
        return "suspeito"
    if p.limite_min is None and p.limite_max is None:
        return "sem limite"
    if p.limite_min is not None and valor < p.limite_min:
        return "nao conforme"
    if p.limite_max is not None and valor > p.limite_max:
        return "nao conforme"
    return "conforme"


def valor_plausivel(chave: str, valor: float) -> bool:
    """True se o valor cai dentro da faixa de plausibilidade fisica do parametro."""
    if valor is None or (isinstance(valor, float) and (valor != valor)):
        return False
    p = PARAMS_POR_CHAVE.get(chave)
    if p is None:
        return True
    if p.zero_invalido and valor == 0:
        return False
    if p.plausivel_min is not None and valor < p.plausivel_min:
        return False
    if p.plausivel_max is not None and valor > p.plausivel_max:
        return False
    return True


def mascarar_implausiveis(df):
    """Substitui valores fisicamente implausiveis por NaN, coluna a coluna."""
    import numpy as np
    df = df.copy()
    for p in PARAMETROS:
        if p.chave not in df.columns:
            continue
        col = df[p.chave]
        mask_invalido = col.isna()
        if p.zero_invalido:
            mask_invalido = mask_invalido | (col == 0)
        if p.plausivel_min is not None:
            mask_invalido = mask_invalido | (col < p.plausivel_min)
        if p.plausivel_max is not None:
            mask_invalido = mask_invalido | (col > p.plausivel_max)
        df.loc[mask_invalido, p.chave] = np.nan
    return df
