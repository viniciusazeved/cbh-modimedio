# Deploy do MODIMEDIO em servidor

Instruções para rodar o painel num PC servidor (rede interna ou exposto via ngrok).

## Arquivos necessários

```
CBH_Modimedio/
├── painel.py
├── loader.py
├── ftp_client.py
├── parser.py
├── stations.py
├── limites.py
├── pyproject.toml
├── uv.lock
├── .env                 # credenciais FTP
├── logo/
└── SHP/
```

`data/cache/` é criada automaticamente.

## Instalação

### 1. UV (se ainda não instalado)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Sincronizar ambiente

```powershell
cd C:\caminho\para\CBH_Modimedio
uv python install 3.11
uv sync
```

### 3. Subir o painel

```powershell
$env:PYTHONUTF8=1
.venv\Scripts\python -m streamlit run painel.py --server.headless true
```

Sobe em `http://localhost:8501`. Para acesso da rede interna, use o IP do servidor.

## Iniciar com o Windows

Crie `iniciar_painel.bat`:

```bat
@echo off
set PYTHONUTF8=1
cd /d C:\caminho\para\CBH_Modimedio
.venv\Scripts\python -m streamlit run painel.py --server.headless true
```

Atalho dele em `shell:startup` (Win+R → `shell:startup`).

## Acesso externo (opcional)

```powershell
winget install ngrok.ngrok
ngrok http 8501
```

Para URL fixa: conta paga ngrok, deploy no Streamlit Community Cloud, ou Cloudflare Tunnel.

## Troubleshooting

- **Falha de TLS no FTP.** O servidor SIGA usa certificado auto-assinado;
  o cliente já está configurado com `CERT_NONE`. Não alterar.
- **Cache "preso".** Apague `data/cache/*.dat` e recarregue o painel.
- **`use_container_width` deprecation warning.** Apenas warning de Streamlit ≥ 1.39 — sem impacto funcional.
