"""
Painel de Monitoramento Qualitativo em Tempo Real
Comite de Bacia Hidrografica do Medio Paraiba do Sul (CBH-MPS)

Streamlit + Plotly + Folium
"""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

import io
import json
import zipfile

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

import limites
import loader
from tempo import agora
from limites import (
    PARAMETROS,
    PARAMS_AUX,
    PARAMS_POR_CHAVE,
    PARAMS_QUALIDADE,
    status_classe_ii,
)
from stations import ESTACOES, ESTACOES_POR_CODIGO


# =============================================================================
# CONFIG
# =============================================================================

st.set_page_config(
    page_title="MODIMEDIO - CBH MPS",
    page_icon="logo/LOGO - CBH MPS_colorida.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sem .git aqui ainda — barrar a animacao de balao do streamlit
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.4rem; padding-bottom: 1rem;}
    [data-testid="stMetricValue"] {font-size: 1.6rem;}
    .status-conforme {color:#198754; font-weight:600;}
    .status-naoconforme {color:#dc3545; font-weight:600;}
    .status-semdado {color:#6c757d; font-weight:600;}
    .status-semlimite {color:#0d6efd; font-weight:600;}
    .status-suspeito {color:#fd7e14; font-weight:600;}
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# UTILS
# =============================================================================

CORES_STATUS = {
    "conforme": "#198754",
    "nao conforme": "#dc3545",
    "suspeito": "#fd7e14",
    "sem dado": "#6c757d",
    "sem limite": "#0d6efd",
}


def fmt_br(valor, decimais=2):
    if valor is None or pd.isna(valor):
        return "—"
    s = f"{valor:,.{decimais}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def status_geral_estacao(df_estacao: pd.DataFrame) -> str:
    """Avalia a ultima leitura de cada parametro qualitativo da CONAMA Classe II."""
    if df_estacao.empty:
        return "sem dado"
    qual = [c for c in PARAMS_QUALIDADE if PARAMS_POR_CHAVE[c].limite_min is not None or PARAMS_POR_CHAVE[c].limite_max is not None]
    statuses = []
    for col in qual:
        if col not in df_estacao.columns:
            continue
        sub = df_estacao.dropna(subset=[col])
        if sub.empty:
            continue
        valor = sub.iloc[-1][col]
        statuses.append(status_classe_ii(col, valor))
    if not statuses:
        return "sem dado"
    if "nao conforme" in statuses:
        return "nao conforme"
    if "conforme" in statuses:
        return "conforme"
    return "sem dado"


def status_card_estacao(df_estacao: pd.DataFrame) -> tuple[str, str, pd.Timestamp | None]:
    """
    Devolve (chip_label, cor, ts_ultima_leitura_sonda).
    Considera 'sonda inativa' se a ultima leitura valida de qualquer parametro
    qualitativo for mais antiga que 2 horas.
    """
    if df_estacao.empty:
        return ("SEM DADO", CORES_STATUS["sem dado"], None)

    sonda_cols = [c for c in PARAMS_QUALIDADE if c in df_estacao.columns]
    df_sonda = df_estacao.dropna(subset=sonda_cols, how="all") if sonda_cols else pd.DataFrame()
    ts_sonda = df_sonda["TIMESTAMP"].iloc[-1] if len(df_sonda) else None

    if ts_sonda is None or pd.isna(ts_sonda):
        return ("SEM LEITURA DA SONDA", CORES_STATUS["sem dado"], None)

    if (agora() - ts_sonda) > timedelta(hours=2):
        return (f"SONDA INATIVA {horas_atras(ts_sonda).upper()}", CORES_STATUS["suspeito"], ts_sonda)

    status = status_geral_estacao(df_estacao)
    return (status.upper(), CORES_STATUS[status], ts_sonda)


def horas_atras(timestamp: pd.Timestamp) -> str:
    if pd.isna(timestamp):
        return "—"
    delta = agora() - timestamp
    if delta < timedelta(minutes=1):
        return "agora"
    if delta < timedelta(hours=1):
        return f"ha {int(delta.total_seconds() // 60)} min"
    if delta < timedelta(days=1):
        return f"ha {int(delta.total_seconds() // 3600)} h"
    return f"ha {delta.days} dias"


def grafico_temporal(
    df: pd.DataFrame,
    parametro: str,
    estacao_nome: str | None = None,
    incluir_banda: bool = True,
):
    """Grafico de linha temporal com banda de limite CONAMA Classe II quando disponivel."""
    p = PARAMS_POR_CHAVE.get(parametro)
    if p is None or parametro not in df.columns:
        return None

    if estacao_nome:
        sub = df[df["estacao"] == estacao_nome]
    else:
        sub = df

    sub = sub.dropna(subset=[parametro])
    if sub.empty:
        return None

    fig = go.Figure()

    if estacao_nome:
        fig.add_trace(go.Scatter(
            x=sub["TIMESTAMP"],
            y=sub[parametro],
            mode="lines",
            name=f"{p.rotulo}",
            line=dict(color=p.cor_grafico, width=2),
            hovertemplate=f"%{{x|%d/%m %H:%M}}<br>{p.rotulo}: %{{y:.2f}} {p.unidade}<extra></extra>",
        ))
    else:
        for est in ESTACOES:
            s = sub[sub["estacao"] == est.nome]
            if s.empty:
                continue
            fig.add_trace(go.Scatter(
                x=s["TIMESTAMP"],
                y=s[parametro],
                mode="lines",
                name=est.nome,
                line=dict(color=est.cor, width=2),
                hovertemplate=f"<b>{est.nome}</b><br>%{{x|%d/%m %H:%M}}<br>%{{y:.2f}} {p.unidade}<extra></extra>",
            ))

    if incluir_banda and (p.limite_min is not None or p.limite_max is not None):
        if p.limite_min is not None:
            fig.add_hline(
                y=p.limite_min,
                line_dash="dash",
                line_color="#dc3545",
                annotation_text=f"Min CONAMA: {p.limite_min}",
                annotation_position="top right",
            )
        if p.limite_max is not None:
            fig.add_hline(
                y=p.limite_max,
                line_dash="dash",
                line_color="#dc3545",
                annotation_text=f"Max CONAMA: {p.limite_max}",
                annotation_position="bottom right",
            )

        # Sombrear faixa fora do conforme
        ymin_data = sub[parametro].min()
        ymax_data = sub[parametro].max()
        if p.limite_max is not None and ymax_data > p.limite_max:
            fig.add_hrect(
                y0=p.limite_max, y1=max(ymax_data, p.limite_max) * 1.05,
                fillcolor="rgba(220,53,69,0.08)", line_width=0,
            )
        if p.limite_min is not None and ymin_data < p.limite_min:
            fig.add_hrect(
                y0=min(ymin_data, p.limite_min) * 0.95, y1=p.limite_min,
                fillcolor="rgba(220,53,69,0.08)", line_width=0,
            )

    titulo = f"{p.rotulo}"
    if p.unidade:
        titulo += f" ({p.unidade})"
    fig.update_layout(
        title=titulo,
        height=320,
        hovermode="x unified",
        margin=dict(l=10, r=10, t=50, b=10),
        xaxis_title="Data/Hora",
        yaxis_title=p.unidade or p.rotulo,
        legend=dict(orientation="h", y=-0.18),
    )
    return fig


# =============================================================================
# CARGA
# =============================================================================

if "atualizacoes" not in st.session_state:
    st.session_state.atualizacoes = 0
    st.session_state.ultima_atualizacao = agora()

with st.spinner("Baixando dados das estacoes via FTPS..."):
    try:
        df_full, metadados = loader.carregar_dados_estacoes(_ttl_token=st.session_state.atualizacoes)
        df_pontos = loader.pontos_com_estacoes()
        erro_carga = None
    except Exception as e:
        df_full = pd.DataFrame()
        metadados = {}
        df_pontos = pd.DataFrame()
        erro_carga = str(e)


# =============================================================================
# SIDEBAR
# =============================================================================

st.sidebar.image("logo/LOGO - CBH MPS_colorida.png", width=180)
st.sidebar.title("MODIMEDIO")
st.sidebar.caption("Monitoramento qualitativo em tempo real")
st.sidebar.markdown("**CBH-MPS · GT SIGA**")
st.sidebar.divider()

pagina = st.sidebar.radio(
    "Navegacao",
    ["Visao Geral", "Por Estacao", "Comparativo entre Estacoes", "Sobre"],
    index=0,
)

# Scroll-to-top quando mudar de pagina (resolve problema de abrir no meio da pagina)
if "pagina_anterior" not in st.session_state:
    st.session_state.pagina_anterior = pagina
if st.session_state.pagina_anterior != pagina:
    st.session_state.pagina_anterior = pagina
    components.html(
        """
        <script>
            const doc = window.parent.document;
            doc.querySelectorAll('section.main, [data-testid="stMain"], [data-testid="stAppViewContainer"]').forEach(el => {
                el.scrollTo({top: 0, behavior: 'instant'});
            });
            window.parent.scrollTo({top: 0, behavior: 'instant'});
        </script>
        """,
        height=0,
        width=0,
    )

st.sidebar.divider()

if st.sidebar.button("Atualizar dados agora", width="stretch"):
    loader.forcar_atualizacao()
    st.session_state.atualizacoes += 1
    st.session_state.ultima_atualizacao = agora()
    st.rerun()

st.sidebar.caption(f"Cache atualizado: {st.session_state.ultima_atualizacao.strftime('%d/%m/%Y %H:%M')}")
st.sidebar.caption("Re-coleta automatica a cada 5 min (TTL do cache).")

st.sidebar.divider()


def _zip_dat_brutos() -> bytes:
    """Empacota os 3 .dat brutos do cache num ZIP em memoria."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for est in ESTACOES:
            arq = Path("data/cache") / est.arquivo_dat
            if arq.exists():
                zf.write(arq, arcname=est.arquivo_dat)
    return buf.getvalue()


with st.sidebar.expander("Baixar dados", expanded=False):
    st.caption("Arquivos brutos vindos do FTP do SIGA-AGEVAP (formato TOA5).")

    st.download_button(
        label="ZIP - 3 estacoes (.dat brutos)",
        data=_zip_dat_brutos(),
        file_name=f"modimedio_dat_{agora().strftime('%Y%m%d_%H%M')}.zip",
        mime="application/zip",
        width="stretch",
        help="Empacota Dados_Estacao_P1/P2/P3.dat (cache local da ultima coleta)",
    )

    if not df_full.empty:
        csv_full = df_full.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="CSV consolidado (3 estacoes)",
            data=csv_full,
            file_name=f"modimedio_consolidado_{agora().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            width="stretch",
            help="Tabela longa com todas as 3 estacoes e colunas de metadados",
        )

with st.sidebar.expander("Sobre os dados", expanded=False):
    st.markdown(
        """
        - Dados de **3 sondas multiparametro** instaladas em ETAs do CBH-MPS.
        - Coleta a cada **5 minutos** via datalogger Campbell CR300.
        - Transmissao para FTP do SIGA-AGEVAP.
        - Limites: **CONAMA 357/2005, Art. 15** (aguas doces Classe II).
        """
    )

st.sidebar.caption("CBH Medio Paraiba do Sul")
st.sidebar.caption(f"Atualizado em maio/{agora().year}")


# =============================================================================
# ERRO DE CARGA
# =============================================================================

if erro_carga:
    st.error(f"Falha ao baixar dados do FTP: {erro_carga}")
    st.info("Verifique credenciais em `.env` e conectividade com o servidor.")
    st.stop()


# =============================================================================
# PAGINA: VISAO GERAL
# =============================================================================

if pagina == "Visao Geral":
    st.title("Monitoramento qualitativo do Medio Paraiba do Sul")
    st.caption("3 estacoes em tempo real · Limites: CONAMA 357/2005 - Aguas doces Classe II")

    # KPI por estacao
    col1, col2, col3 = st.columns(3)
    cols = [col1, col2, col3]
    for col, est in zip(cols, ESTACOES):
        df_est = df_full[df_full["codigo"] == est.codigo]
        chip_label, chip_cor, ts_sonda = status_card_estacao(df_est)
        sonda_inativa = ts_sonda is not None and pd.notna(ts_sonda) and (agora() - ts_sonda) > timedelta(hours=2)

        # Ultima telemetria do datalogger (qualquer linha do .dat)
        ult = df_est.dropna(subset=["TIMESTAMP"]).tail(1)
        ts_logger = ult["TIMESTAMP"].iloc[0] if len(ult) else pd.NaT

        # ultima leitura por parametro (com seu proprio timestamp)
        ph_row = df_est.dropna(subset=["pH"]).tail(1)
        od_row = df_est.dropna(subset=["OD"]).tail(1)
        turb_row = df_est.dropna(subset=["Turb"]).tail(1)

        with col:
            st.subheader(est.nome)
            st.caption(f"{est.municipio} · {est.operadora}")
            st.markdown(
                f"<span style='background:{chip_cor}20; color:{chip_cor}; padding:4px 10px; "
                f"border-radius:6px; font-weight:600;'>● {chip_label}</span>",
                unsafe_allow_html=True,
            )
            st.caption(
                f"Datalogger: {ts_logger.strftime('%d/%m %H:%M') if pd.notna(ts_logger) else '—'} "
                f"({horas_atras(ts_logger)})"
            )
            if pd.notna(ts_sonda):
                cor_sonda = CORES_STATUS["suspeito"] if sonda_inativa else "#6c757d"
                st.markdown(
                    f"<span style='font-size:0.85em; color:{cor_sonda};'>"
                    f"Sonda da agua: {ts_sonda.strftime('%d/%m %H:%M')} ({horas_atras(ts_sonda)})"
                    f"</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<span style='font-size:0.85em; color:#6c757d;'>"
                    "Sonda da agua: sem leitura valida</span>",
                    unsafe_allow_html=True,
                )

            sub_cols = st.columns(3)

            def _kpi(coluna, label, row, col_chave, decimais):
                with coluna:
                    if len(row):
                        valor = row[col_chave].iloc[0]
                        ts = row["TIMESTAMP"].iloc[0]
                        st.metric(label, fmt_br(valor, decimais))
                        idade_h = (agora() - ts).total_seconds() / 3600
                        cor_ts = CORES_STATUS["suspeito"] if idade_h > 2 else "#6c757d"
                        st.markdown(
                            f"<span style='font-size:0.75em; color:{cor_ts};'>"
                            f"{ts.strftime('%d/%m %H:%M')}</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.metric(label, "—")
                        st.markdown(
                            "<span style='font-size:0.75em; color:#6c757d;'>sem leitura</span>",
                            unsafe_allow_html=True,
                        )

            _kpi(sub_cols[0], "pH", ph_row, "pH", 2)
            _kpi(sub_cols[1], "OD (mg/L)", od_row, "OD", 1)
            _kpi(sub_cols[2], "Turb (NTU)", turb_row, "Turb", 1)

    st.divider()

    col_mapa, col_resumo = st.columns([2, 1])

    with col_mapa:
        st.subheader("Mapa de monitoramento")
        st.caption("Bacia do Medio Paraiba do Sul. Cor do marcador = situacao na ultima leitura (CONAMA Classe II).")

        if not df_pontos.empty:
            centro_lat = df_pontos["lat"].mean()
            centro_lon = df_pontos["lon"].mean()
            m = folium.Map(location=[centro_lat, centro_lon], zoom_start=9, tiles="OpenStreetMap")

            # Limite RH3 (Medio Paraiba do Sul) como camada de fundo
            gdf_rh3 = loader.carregar_limite_rh3()
            if gdf_rh3 is not None:
                folium.GeoJson(
                    gdf_rh3.to_json(),
                    name="RH-III - Medio Paraiba do Sul",
                    style_function=lambda _: {
                        "color": "#0d6efd",
                        "weight": 2.5,
                        "fillColor": "#0d6efd",
                        "fillOpacity": 0.07,
                        "dashArray": "6, 4",
                    },
                    tooltip=folium.Tooltip("Regiao Hidrografica III - Medio Paraiba do Sul (RH3)"),
                ).add_to(m)
                # Ajusta enquadramento do mapa para a bacia inteira
                xmin, ymin, xmax, ymax = gdf_rh3.total_bounds
                m.fit_bounds([[ymin, xmin], [ymax, xmax]], padding=(20, 20))

            for _, row in df_pontos.iterrows():
                df_est = df_full[df_full["codigo"] == row["codigo"]]
                chip_label, cor, ts_sonda = status_card_estacao(df_est)

                # popup com mini-resumo
                ph_val = df_est.dropna(subset=["pH"])["pH"].iloc[-1] if df_est["pH"].notna().any() else None
                od_val = df_est.dropna(subset=["OD"])["OD"].iloc[-1] if df_est["OD"].notna().any() else None
                turb_val = df_est.dropna(subset=["Turb"])["Turb"].iloc[-1] if df_est["Turb"].notna().any() else None

                ts_str = ts_sonda.strftime('%d/%m %H:%M') if ts_sonda is not None and pd.notna(ts_sonda) else '—'
                popup_html = f"""
                <div style='font-family: sans-serif; min-width: 220px;'>
                    <b style='font-size:1.05em;'>{row['nome']}</b><br>
                    <span style='color:#666;'>{row['Municipio']} · {row['Concession']}</span><br>
                    <hr style='margin:6px 0;'>
                    <b>Status:</b> <span style='color:{cor};'>{chip_label}</span><br>
                    <b>pH:</b> {fmt_br(ph_val, 2)}<br>
                    <b>OD:</b> {fmt_br(od_val, 1)} mg/L<br>
                    <b>Turbidez:</b> {fmt_br(turb_val, 1)} NTU<br>
                    <span style='color:#666;font-size:0.85em;'>Sonda da agua: {ts_str}</span>
                </div>
                """
                folium.CircleMarker(
                    location=[row["lat"], row["lon"]],
                    radius=12,
                    popup=folium.Popup(popup_html, max_width=280),
                    tooltip=row["nome"],
                    color="white",
                    weight=2,
                    fill=True,
                    fill_color=cor,
                    fill_opacity=0.9,
                ).add_to(m)

                folium.Marker(
                    location=[row["lat"], row["lon"]],
                    icon=folium.DivIcon(
                        html=f"<div style='font-size:11px;font-weight:600;color:#222;text-shadow:0 0 3px white;margin-left:14px;'>{row['nome']}</div>"
                    ),
                ).add_to(m)

            st_folium(m, height=480, width=None, returned_objects=[])

    with col_resumo:
        st.subheader("Resumo CONAMA Classe II")
        for est in ESTACOES:
            df_est = df_full[df_full["codigo"] == est.codigo]
            with st.expander(est.nome, expanded=True):
                for chave in PARAMS_QUALIDADE:
                    p = PARAMS_POR_CHAVE[chave]
                    sub = df_est.dropna(subset=[chave])
                    if sub.empty:
                        st.markdown(f"**{p.rotulo}:** <span class='status-semdado'>sem dado</span>", unsafe_allow_html=True)
                        continue
                    valor = sub.iloc[-1][chave]
                    status = status_classe_ii(chave, valor)
                    cor = CORES_STATUS[status]
                    st.markdown(
                        f"**{p.rotulo}:** {fmt_br(valor, 2)} {p.unidade} "
                        f"<span style='color:{cor}; font-weight:600;'>● {status}</span>",
                        unsafe_allow_html=True,
                    )

    st.divider()

    # Diagnostico operacional - cobertura por estacao/parametro
    with st.expander("Diagnostico operacional das sondas (cobertura real por parametro)", expanded=False):
        st.caption(
            "Apos filtros de plausibilidade fisica (faixa esperada de cada parametro + zeros literais "
            "tratados como sonda apagada), abaixo ficam os intervalos REAIS de leitura por sonda. "
            "Util para identificar lacunas, calibracao errada e sondas fora d'agua."
        )
        df_diag = loader.diagnostico_operacional(df_full)
        if not df_diag.empty:
            df_diag_show = df_diag.copy()
            df_diag_show["Inicio"] = df_diag_show["Inicio"].apply(
                lambda x: x.strftime("%d/%m %H:%M") if pd.notna(x) else "—"
            )
            df_diag_show["Fim"] = df_diag_show["Fim"].apply(
                lambda x: x.strftime("%d/%m %H:%M") if pd.notna(x) else "—"
            )
            df_diag_show.columns = ["Estacao", "Parametro", "N validos", "Inicio leituras", "Fim leituras", "Cobertura %"]
            st.dataframe(df_diag_show, width="stretch", hide_index=True)
        st.caption(
            "**Faixas de plausibilidade aplicadas:** pH 4-11 · OD 0-14 mg/L · Turbidez 0-4000 NTU · "
            "Temperatura 0-50 °C · Condutividade 0-2000 µS/cm · ORP -1000 a 1000 mV. "
            "Valores fora dessas faixas sao mascarados como sem leitura, pois indicam erro de calibracao."
        )

    st.divider()

    # Linha temporal - janela ajustavel
    st.subheader("Serie temporal - parametros qualitativos")
    janelas_home = {
        "Ultimas 24h": timedelta(days=1),
        "Ultimos 3 dias": timedelta(days=3),
        "Ultimos 7 dias": timedelta(days=7),
        "Tudo": None,
    }
    janela_home = st.radio("Janela:", list(janelas_home.keys()), horizontal=True, index=2, key="janela_home")
    if janelas_home[janela_home] is not None:
        df_janela = df_full[df_full["TIMESTAMP"] >= agora() - janelas_home[janela_home]]
    else:
        df_janela = df_full

    if df_janela.empty:
        st.info("Sem dados na janela selecionada.")
    else:
        for chave in PARAMS_QUALIDADE:
            fig = grafico_temporal(df_janela, chave)
            if fig is not None:
                # Estacoes ausentes na janela ganham legenda explicativa
                presentes = set(df_janela.dropna(subset=[chave])["estacao"].unique())
                ausentes = [e.nome for e in ESTACOES if e.nome not in presentes]
                if ausentes:
                    fig.add_annotation(
                        text=f"Sem dados na janela: {', '.join(ausentes)}",
                        xref="paper", yref="paper", x=0, y=1.08, showarrow=False,
                        font=dict(size=11, color="#6c757d"),
                        align="left",
                    )
                st.plotly_chart(fig, width="stretch")
            else:
                p = PARAMS_POR_CHAVE[chave]
                st.info(f"Nenhuma das 3 estacoes registrou {p.rotulo} na janela selecionada.")


# =============================================================================
# PAGINA: POR ESTACAO
# =============================================================================

elif pagina == "Por Estacao":
    st.title("Detalhamento por estacao")
    nomes = [e.nome for e in ESTACOES]
    sel = st.radio("Estacao:", nomes, horizontal=True)
    est = next(e for e in ESTACOES if e.nome == sel)
    df_est = df_full[df_full["codigo"] == est.codigo].copy()

    meta = metadados.get(est.codigo, {})
    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        st.subheader(est.nome)
        st.caption(f"{est.municipio} · {est.operadora}")
    with col_b:
        st.metric("Modelo do datalogger", meta.get("modelo", "—"))
    with col_c:
        ult = df_est.dropna(subset=["TIMESTAMP"]).tail(1)
        ts = ult["TIMESTAMP"].iloc[0] if len(ult) else pd.NaT
        st.metric("Ultima telemetria", ts.strftime("%d/%m %H:%M") if pd.notna(ts) else "—")

    st.divider()

    # KPIs - 6 parametros qualitativos
    st.subheader("Ultima leitura - parametros de qualidade")
    cols = st.columns(len(PARAMS_QUALIDADE))
    for col, chave in zip(cols, PARAMS_QUALIDADE):
        p = PARAMS_POR_CHAVE[chave]
        sub = df_est.dropna(subset=[chave])
        if sub.empty:
            with col:
                st.metric(p.rotulo, "—")
                st.caption("sem dado")
            continue
        valor = sub.iloc[-1][chave]
        status = status_classe_ii(chave, valor)
        with col:
            st.metric(f"{p.rotulo} ({p.unidade})" if p.unidade else p.rotulo, fmt_br(valor, 2))
            cor = CORES_STATUS[status]
            st.markdown(
                f"<span style='color:{cor}; font-weight:600;'>● {status}</span>",
                unsafe_allow_html=True,
            )

    st.divider()

    # Filtro de janela
    st.subheader("Serie temporal")
    janelas = {
        "Ultimas 24h": timedelta(days=1),
        "Ultimos 3 dias": timedelta(days=3),
        "Ultimos 7 dias": timedelta(days=7),
        "Tudo": None,
    }
    janela_sel = st.radio("Janela:", list(janelas.keys()), horizontal=True, index=2)
    if janelas[janela_sel] is not None:
        df_plot = df_est[df_est["TIMESTAMP"] >= agora() - janelas[janela_sel]]
    else:
        df_plot = df_est

    # Tabs: qualidade x auxiliares
    aba_qual, aba_aux, aba_violacoes, aba_dados = st.tabs(
        ["Qualidade da agua", "Meteorologia / operacional", "Violacoes CONAMA", "Tabela bruta"]
    )

    with aba_qual:
        for chave in PARAMS_QUALIDADE:
            fig = grafico_temporal(df_plot, chave, estacao_nome=est.nome)
            if fig is not None:
                st.plotly_chart(fig, width="stretch")
            else:
                p = PARAMS_POR_CHAVE[chave]
                st.info(f"Sem dados para {p.rotulo} na janela selecionada.")

    with aba_aux:
        for chave in PARAMS_AUX:
            fig = grafico_temporal(df_plot, chave, estacao_nome=est.nome, incluir_banda=False)
            if fig is not None:
                st.plotly_chart(fig, width="stretch")
            else:
                p = PARAMS_POR_CHAVE[chave]
                st.info(f"Sem dados para {p.rotulo} na janela selecionada.")

    with aba_violacoes:
        registros = []
        for chave in PARAMS_QUALIDADE:
            p = PARAMS_POR_CHAVE[chave]
            if p.limite_min is None and p.limite_max is None:
                continue
            sub = df_plot.dropna(subset=[chave])
            if sub.empty:
                continue
            for _, row in sub.iterrows():
                v = row[chave]
                viol = False
                tipo = ""
                if p.limite_min is not None and v < p.limite_min:
                    viol, tipo = True, f"abaixo do minimo ({p.limite_min})"
                elif p.limite_max is not None and v > p.limite_max:
                    viol, tipo = True, f"acima do maximo ({p.limite_max})"
                if viol:
                    registros.append({
                        "Data/Hora": row["TIMESTAMP"],
                        "Parametro": p.rotulo,
                        "Valor": v,
                        "Unidade": p.unidade,
                        "Violacao": tipo,
                    })
        if registros:
            df_viol = pd.DataFrame(registros).sort_values("Data/Hora", ascending=False)
            st.warning(f"**{len(df_viol)}** registro(s) fora do padrao Classe II na janela selecionada.")
            st.dataframe(df_viol, width="stretch", hide_index=True)
            csv = df_viol.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "Baixar violacoes (CSV)",
                data=csv,
                file_name=f"violacoes_{est.codigo}_{janela_sel.replace(' ', '_').lower()}.csv",
                mime="text/csv",
            )
        else:
            st.success("Sem violacoes do padrao Classe II na janela selecionada.")

    with aba_dados:
        st.dataframe(df_plot.sort_values("TIMESTAMP", ascending=False), width="stretch", hide_index=True)
        csv = df_plot.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Baixar dados completos (CSV)",
            data=csv,
            file_name=f"dados_{est.codigo}.csv",
            mime="text/csv",
        )


# =============================================================================
# PAGINA: COMPARATIVO
# =============================================================================

elif pagina == "Comparativo entre Estacoes":
    st.title("Comparativo entre estacoes")
    st.caption("Sobreposicao temporal das 3 estacoes para um parametro selecionado.")

    rotulos = {p.chave: f"{p.rotulo}" + (f" ({p.unidade})" if p.unidade else "") for p in PARAMETROS}
    chaves_disp = PARAMS_QUALIDADE + PARAMS_AUX
    chave_sel = st.selectbox(
        "Parametro:",
        options=chaves_disp,
        format_func=lambda c: rotulos[c],
        index=0,
    )

    janelas = {
        "Ultimas 24h": timedelta(days=1),
        "Ultimos 3 dias": timedelta(days=3),
        "Ultimos 7 dias": timedelta(days=7),
        "Tudo": None,
    }
    janela_sel = st.radio("Janela:", list(janelas.keys()), horizontal=True, index=2)
    if janelas[janela_sel] is not None:
        df_plot = df_full[df_full["TIMESTAMP"] >= agora() - janelas[janela_sel]]
    else:
        df_plot = df_full

    p = PARAMS_POR_CHAVE[chave_sel]
    incluir_banda = p.limite_min is not None or p.limite_max is not None
    fig = grafico_temporal(df_plot, chave_sel, estacao_nome=None, incluir_banda=incluir_banda)
    if fig is None:
        st.info("Sem dados para o parametro/janela selecionados.")
    else:
        fig.update_layout(height=500)
        st.plotly_chart(fig, width="stretch")

    # Estatisticas comparativas
    st.subheader("Estatisticas no periodo")
    rows = []
    for est in ESTACOES:
        sub = df_plot[df_plot["codigo"] == est.codigo].dropna(subset=[chave_sel])
        if sub.empty:
            rows.append({"Estacao": est.nome, "n": 0, "Min": None, "Max": None, "Media": None, "Mediana": None})
        else:
            rows.append({
                "Estacao": est.nome,
                "n": int(sub.shape[0]),
                "Min": float(sub[chave_sel].min()),
                "Max": float(sub[chave_sel].max()),
                "Media": float(sub[chave_sel].mean()),
                "Mediana": float(sub[chave_sel].median()),
            })
    df_stats = pd.DataFrame(rows)
    st.dataframe(df_stats, width="stretch", hide_index=True)


# =============================================================================
# PAGINA: SOBRE
# =============================================================================

elif pagina == "Sobre":
    st.title("Sobre o painel")

    st.markdown(
        """
        Este painel consolida em tempo real (intervalo de **5 minutos**) os dados de **3 sondas
        multiparametro** instaladas em estacoes de tratamento de agua (ETAs) operadas por
        concessionarias parceiras do **Comite de Bacia Hidrografica do Medio Paraiba do Sul (CBH-MPS)**.

        Os dados brutos sao gerados por dataloggers Campbell Scientific CR300 e transmitidos
        via FTPS (FTP sobre TLS) para o servidor SIGA-AGEVAP.

        ### Estacoes monitoradas
        """
    )
    df_est = pd.DataFrame([
        {"Codigo": e.codigo, "Estacao": e.nome, "Municipio": e.municipio, "Operadora": e.operadora}
        for e in ESTACOES
    ])
    st.dataframe(df_est, width="stretch", hide_index=True)

    st.divider()

    st.subheader("Limites - CONAMA 357/2005, Art. 15 (aguas doces Classe II)")
    df_lim = pd.DataFrame([
        {
            "Parametro": p.rotulo,
            "Unidade": p.unidade or "—",
            "Min": f"{p.limite_min:g}" if p.limite_min is not None else "—",
            "Max": f"{p.limite_max:g}" if p.limite_max is not None else "—",
            "Descricao": p.descricao,
        }
        for p in PARAMETROS
        if p.chave in PARAMS_QUALIDADE
    ])
    st.dataframe(df_lim, width="stretch", hide_index=True)

    st.markdown(
        """
        > **Nota.** A Resolucao CONAMA 357/2005 estabelece limites para aguas doces Classe II,
        > destinadas, dentre outros usos, ao **abastecimento humano apos tratamento convencional**.
        > Parametros sem limite numerico fixo na resolucao (Cond, ORP, Temperatura) sao exibidos
        > como informativos e podem indicar tendencias antes que parametros regulados sejam excedidos.
        """
    )

    st.divider()
    st.caption("CBH Medio Paraiba do Sul · GT SIGA · Dados: SIGA-AGEVAP")
