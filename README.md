# MODIMEDIO — Painel de Monitoramento Qualitativo em Tempo Real

Painel Streamlit que consolida em tempo real os dados de **3 sondas multiparâmetro**
instaladas em ETAs do **Comitê de Bacia Hidrográfica do Médio Paraíba do Sul (CBH-MPS)**.

Telemetria a cada 5 minutos via dataloggers Campbell CR300 → FTPS do SIGA-AGEVAP →
parser TOA5 → painel em Streamlit + Folium + Plotly.

Limites de qualidade: **CONAMA 357/2005 — águas doces Classe II**.

## Estações monitoradas

| Código | Estação        | Município          | Operadora                |
|--------|----------------|--------------------|--------------------------|
| P1     | ETA Belmonte   | Volta Redonda      | SAAE-VR                  |
| P2     | ETA Principal  | Paraíba do Sul     | Águas da Condessa        |
| P3     | ETA Toyota     | Resende            | Água das Agulhas Negras  |

> A correspondência P1↔Belmonte vem do cabeçalho TOA5 do `.dat`.
> P2 e P3 estão como genéricos no FTP e foram mapeados em ordem alfabética.
> Para corrigir, edite `stations.py`.

## Estrutura do projeto

```
CBH_Modimedio/
├── painel.py            # entry-point Streamlit
├── loader.py            # orquestra FTP -> parse -> dataframe consolidado
├── ftp_client.py        # cliente FTPS com cache em disco
├── parser.py            # parser TOA5 (Campbell Scientific)
├── stations.py          # config das 3 estações
├── limites.py           # limites CONAMA 357 Classe II
├── pyproject.toml       # dependências (uv)
├── .env                 # credenciais FTP (NÃO comitar)
├── .env.example
├── data/cache/          # cache local dos .dat baixados
├── logo/                # logos do CBH-MPS
└── SHP/                 # shapefile MODIMEDIO UMRs
```

## Rodar localmente

```powershell
# Instalar dependências (Python 3.11+)
uv sync

# Configurar credenciais
cp .env.example .env
# (já vem preenchido com as credenciais do SIGA)

# Subir o painel
$env:PYTHONUTF8=1
.venv\Scripts\python -m streamlit run painel.py
```

Painel sobe em http://localhost:8501.

## Páginas

- **Visão Geral.** KPIs por estação, mapa Folium com pontos coloridos por status,
  resumo CONAMA Classe II e gráficos das últimas 24h dos 6 parâmetros qualitativos.
- **Por Estação.** Detalhamento completo por estação: KPIs, série temporal por janela
  (24h / 3d / 7d / tudo), abas de qualidade, meteorologia, violações CONAMA e tabela bruta.
- **Comparativo entre Estações.** Sobreposição temporal das 3 estações para um parâmetro
  selecionado, com banda CONAMA e estatísticas (n, min, max, média, mediana).
- **Sobre.** Glossário CONAMA 357/2005 e descrição das estações.

## Cache e atualização

- Os `.dat` são baixados via FTPS e cacheados em `data/cache/` por **5 minutos** (`DEFAULT_TTL_SECONDS`).
- O Streamlit rerenderiza com `@st.cache_data(ttl=300)`.
- Botão **"Atualizar dados agora"** na sidebar força redownload + rerun.

## Deploy em servidor (acesso interno)

Mesmo procedimento do painel `CBH_Uso_do_Solo` — ver `DEPLOY_SERVIDOR.md`.

## Parâmetros monitorados

| Coluna .dat        | Parâmetro                 | Unidade | Limite CONAMA II |
|--------------------|---------------------------|---------|------------------|
| `pH`               | pH                        | —       | 6,0 — 9,0        |
| `OD`               | Oxigênio Dissolvido       | mg/L    | ≥ 5,0            |
| `Turb`             | Turbidez                  | NTU     | ≤ 100            |
| `Temp`             | Temperatura da água       | °C      | sem limite numérico |
| `Cond`             | Condutividade Elétrica    | µS/cm   | informativo      |
| `ORP`              | Potencial Redox           | mV      | informativo      |
| `Prof`             | Profundidade da sonda     | m       | operacional      |
| `ChuvaTotal`       | Chuva acumulada           | mm      | meteorológico    |
| `TempExt`          | Temperatura externa (ar)  | °C      | meteorológico    |
| `UmidadeRelativa`  | Umidade relativa do ar    | %       | meteorológico    |
| `Alimentacao`      | Tensão do datalogger      | V       | 11–15 (saudável) |

## Observações operacionais (na primeira inspeção)

- **ETA Belmonte (P1):** dados frescos, fluxo regular.
- **ETA Principal (P2):** sonda multiparâmetro retornando NaN para todos os parâmetros
  qualitativos (apenas datalogger, ar e bateria estão respondendo). Verificar com a operadora.
- **ETA Toyota (P3):** última leitura válida há ~2 dias; turbidez na última leitura ≈ 288 NTU
  (acima do limite Classe II — possível pico de descarga sólida pós-chuva ou problema na sonda).

## Créditos

CBH Médio Paraíba do Sul · GT SIGA · Dados: SIGA-AGEVAP.
