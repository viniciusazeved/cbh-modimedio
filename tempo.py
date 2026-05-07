"""
Utilidades de fuso horario.

O Streamlit Community Cloud roda em UTC. As sondas TOA5 enviam timestamps
em horario local (America/Sao_Paulo). Esta camada garante que toda
comparacao 'agora vs ultimo timestamp' seja feita em horario de Brasilia,
independentemente de onde o painel esteja hospedado.
"""

from __future__ import annotations

import pandas as pd

TZ_BRASIL = "America/Sao_Paulo"


def agora() -> pd.Timestamp:
    """Retorna o instante atual em horario de Brasilia, como Timestamp naive.

    Os timestamps do .dat tambem sao naive (representam horario local da estacao).
    Devolver naive aqui mantem compatibilidade direta com df['TIMESTAMP'].
    """
    return pd.Timestamp.now(tz=TZ_BRASIL).tz_localize(None)
