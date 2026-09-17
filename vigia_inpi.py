# -*- coding: utf-8 -*-
"""Vigia semanal dos pedidos de marca da Pattrono no INPI.

Roda no GitHub Actions toda terca. Consulta o pePI (situacao de cada processo)
e a RPI da semana (procura os numeros de processo na revista de marcas).
Grava status.json e last_run.md; sinaliza movimento/erro para o workflow.
So usa a biblioteca padrao do Python.
"""
import io
import json
import os
import re
import sys
import zipfile
import hashlib
import urllib.request
import http.cookiejar
from datetime import datetime, timezone, timedelta

PROCESSOS = {
    "944976310": "PATTRONO (nominativa, NCL 35)",
    "944976891": "COSTVISION (nominativa, NCL 42)",
}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
BRT = timezone(timedelta(hours=-3))
AGORA = datetime.now(BRT).strftime("%d/%m/%Y %H:%M")


def abrir(opener, url, timeout=90, tentativas=3):
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with opener.open(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            ultimo = e
            import time
            time.sleep(10 * (i + 1))
    raise ultimo


def texto_limpo(html_latin1):
    t = html_latin1.decode("latin-1", errors="replace")
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;?", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalizar_pepi(t):
    """Extrai o trecho relevante e remove o carimbo de data/hora da consulta."""
    i = t.find("RESULTADO DA PESQUISA")
    j = t.find("ferramenta acess")
    trecho = t[i: j if j > i else i + 700] if i >= 0 else t[:700]
    trecho = re.sub(r"\(\s*\d{2}/\d{2}/\d{4}[^)]*\)", "", trecho)
    return re.sub(r"\s+", " ", trecho).strip()


def consulta_pepi():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    abrir(opener, "https://busca.inpi.gov.br/pePI/")
    abrir(opener, "https://busca.inpi.gov.br/pePI/servlet/LoginController?action=login")
    saida = {}
    for proc in PROCESSOS:
        url = ("https://busca.inpi.gov.br/pePI/servlet/MarcasServletController"
               f"?Action=searchMarca&tipoPesquisa=BY_NUM_PROC&NumPedido={proc}")
        bruto = abrir(opener, url)
        t = normalizar_pepi(texto_limpo(bruto))
        saida[proc] = {
            "texto": t[:900],
            "hash": hashlib.sha1(t.encode("utf-8")).hexdigest(),
        }
    return saida


def rpi_mais_recente():
    dados = abrir(urllib.request.build_opener(), "https://revistas.inpi.gov.br/rpi/")
    nums = [int(n) for n in re.findall(r"\b(2[89]\d{2}|3\d{3})\b", dados.decode("utf-8", "replace"))]
    return max(nums) if nums else None


def busca_na_rpi(numero):
    """Baixa RM{numero}.zip e procura os processos. Retorna dict proc -> True/False."""
    url = f"https://revistas.inpi.gov.br/txt/RM{numero}.zip"
    dados = abrir(urllib.request.build_opener(), url, timeout=300)
    z = zipfile.ZipFile(io.BytesIO(dados))
    achados = {p: False for p in PROCESSOS}
    for nome in z.namelist():
        blob = z.read(nome)
        for p in PROCESSOS:
            if p.encode() in blob:
                achados[p] = True
    return achados


def main():
    anterior = {}
    if os.path.exists("status.json"):
        with open("status.json", encoding="utf-8") as f:
            anterior = json.load(f)

    status = {"verificado_em": AGORA, "erro": None, "movimento": False,
              "rpi": None, "rpi_hits": {}, "pepi": {}, "mudancas": []}
    try:
        status["pepi"] = consulta_pepi()
        num = rpi_mais_recente()
        status["rpi"] = num
        if num:
            ja_vista = anterior.get("rpi")
            if ja_vista != num:
                status["rpi_hits"] = busca_na_rpi(num)
            else:
                status["rpi_hits"] = {p: False for p in PROCESSOS}

        # movimento: texto do pePI mudou OU processo citado na RPI da semana
        for proc, info in status["pepi"].items():
            h_ant = anterior.get("pepi", {}).get(proc, {}).get("hash")
            if h_ant and h_ant != info["hash"]:
                status["movimento"] = True
                status["mudancas"].append(f"pePI mudou para {proc} ({PROCESSOS[proc]})")
        for proc, hit in status["rpi_hits"].items():
            if hit:
                status["movimento"] = True
                status["mudancas"].append(f"Processo {proc} ({PROCESSOS[proc]}) citado na RPI {status['rpi']}")
    except Exception as e:  # noqa: BLE001
        status["erro"] = f"{type(e).__name__}: {e}"
        # preserva a linha de base anterior para a comparacao da proxima semana
        if not status["pepi"]:
            status["pepi"] = anterior.get("pepi", {})
        if status["rpi"] is None:
            status["rpi"] = anterior.get("rpi")

    with open("status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    # resumo humano
    linhas = [f"# Vigia INPI Pattrono — {AGORA} (BRT)", ""]
    if status["erro"]:
        linhas += [f"**FALHA na verificação:** `{status['erro']}`", "",
                   "Verificar manualmente: https://busca.inpi.gov.br/pePI/ "
                   "(pedidos 944976310 e 944976891)."]
    else:
        linhas += [f"RPI verificada: **{status['rpi']}**", ""]
        for proc, nome in PROCESSOS.items():
            hit = status["rpi_hits"].get(proc)
            linhas.append(f"## {nome} — pedido {proc}")
            linhas.append(f"- Citado na RPI desta semana: {'**SIM**' if hit else 'não'}")
            linhas.append(f"- pePI: {status['pepi'][proc]['texto'][:250]}")
            linhas.append("")
        if status["movimento"]:
            linhas += ["## 🔔 MOVIMENTAÇÃO DETECTADA", ""] + [f"- {m}" for m in status["mudancas"]]
            linhas += ["", "Abrir a RPI e o pePI para ler o despacho. Prazos correm da data de publicação na RPI."]
        else:
            linhas.append("Sem movimentação. Silêncio = nenhuma novidade nos dois pedidos.")
    with open("last_run.md", "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")

    with open("historico.md", "a", encoding="utf-8") as f:
        f.write(f"- {AGORA} | RPI {status['rpi']} | movimento={status['movimento']} | erro={status['erro']}\n")

    # sinais para o workflow
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"movimento={'true' if status['movimento'] else 'false'}\n")
            f.write(f"erro={'true' if status['erro'] else 'false'}\n")
    print(json.dumps(status, ensure_ascii=False, indent=2)[:2000])


if __name__ == "__main__":
    main()
