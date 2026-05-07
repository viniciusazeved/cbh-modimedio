"""
Cliente FTPS explicito (FTP_TLS) para baixar os arquivos .dat das 3 estacoes.

Le credenciais de st.secrets (Streamlit Cloud) ou de variaveis de ambiente / .env (local).
Cache em disco com TTL para nao bater no FTP a cada rerun do Streamlit.
"""

from __future__ import annotations

import os
import ssl
import time
from ftplib import FTP_TLS
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TTL_SECONDS = 5 * 60  # 5 min: dado novo a cada 5 min na estacao


def _cred(chave: str, default: str = "") -> str:
    """Le credencial de st.secrets se disponivel, senao de variavel de ambiente."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and chave in st.secrets:
            return str(st.secrets[chave])
    except Exception:
        pass
    return os.getenv(chave, default)


def _build_ftp() -> FTP_TLS:
    host = _cred("FTP_HOST", "54.94.199.217")
    port = int(_cred("FTP_PORT", "21"))
    user = _cred("FTP_USER", "transfer")
    pwd = _cred("FTP_PASS", "")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    ftp = FTP_TLS(context=ctx, timeout=30)
    ftp.connect(host, port)
    ftp.login(user, pwd)
    ftp.prot_p()
    return ftp


def baixar_arquivo(nome_arquivo: str, ttl: int = DEFAULT_TTL_SECONDS, force: bool = False) -> Path:
    """Baixa nome_arquivo do diretorio remoto. Reusa cache em disco se ainda fresco."""
    remote_dir = _cred("FTP_REMOTE_DIR", "/upload")
    destino = CACHE_DIR / nome_arquivo

    if not force and destino.exists():
        idade = time.time() - destino.stat().st_mtime
        if idade < ttl:
            return destino

    ftp = _build_ftp()
    try:
        ftp.cwd(remote_dir)
        with open(destino, "wb") as f:
            ftp.retrbinary(f"RETR {nome_arquivo}", f.write)
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()
    return destino


def baixar_todas(arquivos: list[str], ttl: int = DEFAULT_TTL_SECONDS, force: bool = False) -> dict[str, Path]:
    """Baixa varios arquivos reusando a mesma conexao."""
    remote_dir = _cred("FTP_REMOTE_DIR", "/upload")
    resultado: dict[str, Path] = {}

    # checa cache antes de abrir conexao
    pendentes = []
    for nome in arquivos:
        destino = CACHE_DIR / nome
        if not force and destino.exists() and (time.time() - destino.stat().st_mtime) < ttl:
            resultado[nome] = destino
        else:
            pendentes.append(nome)

    if not pendentes:
        return resultado

    ftp = _build_ftp()
    try:
        ftp.cwd(remote_dir)
        for nome in pendentes:
            destino = CACHE_DIR / nome
            with open(destino, "wb") as f:
                ftp.retrbinary(f"RETR {nome}", f.write)
            resultado[nome] = destino
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()

    return resultado
