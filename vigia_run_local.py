# -*- coding: utf-8 -*-
"""Executor local do vigia: roda a verificacao, publica no GitHub e abre issue se preciso."""
import json
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
GH = r"C:\Program Files\GitHub CLI\gh.exe"
os.chdir(AQUI)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main():
    r = run([sys.executable, "vigia_inpi.py"])
    print(r.stdout[-1500:], r.stderr[-500:])

    with open("status.json", encoding="utf-8") as f:
        status = json.load(f)

    run(["git", "add", "status.json", "last_run.md", "historico.md"])
    diff = run(["git", "diff", "--cached", "--quiet"])
    if diff.returncode != 0:
        run(["git", "commit", "-m", f"Verificacao {status.get('verificado_em','')}"])
        p = run(["git", "push"])
        print("push:", p.returncode, p.stderr[-200:])

    if os.environ.get("CALIBRACAO"):
        print("modo calibracao: sem issue")
        return
    titulo = None
    if status.get("movimento"):
        titulo = f"🔔 Movimentação nos pedidos INPI da Pattrono ({status['verificado_em']})"
    elif status.get("erro"):
        titulo = f"⚠️ Vigia INPI falhou ({status['verificado_em']})"
    if titulo:
        r = run([GH, "issue", "create",
                 "--repo", "gustavofuster95-prog/pattrono-inpi-vigia",
                 "--title", titulo, "--body-file", "last_run.md"])
        print("issue:", r.returncode, (r.stdout or r.stderr)[-200:])


if __name__ == "__main__":
    main()
