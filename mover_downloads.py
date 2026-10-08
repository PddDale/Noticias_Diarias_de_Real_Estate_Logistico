"""
Move os briefings baixados do Colab (pasta Downloads) para ./briefings/.

O Colab roda numa máquina do Google e só consegue entregar os arquivos pelo
download do navegador. Este script faz a ponte no PC:

    python mover_downloads.py              # move o que já está em Downloads
    python mover_downloads.py --vigiar     # fica esperando (30 min) e move ao chegar
    python mover_downloads.py --vigiar 60  # idem, por 60 min

Só mexe em briefing_AAAA-MM-DD_<período>.html/.pdf. Cópias renomeadas pelo
navegador ("briefing_..._48h (1).html") voltam ao nome original e substituem a
versão anterior em briefings/.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

PASTA_SAIDA = Path(__file__).resolve().parent / "briefings"
RE_BRIEFING = re.compile(r"^(briefing_\d{4}-\d{2}-\d{2}_[0-9a-z]+)(?: ?\(\d+\))?\.(html|pdf)$", re.IGNORECASE)
INTERVALO_VIGIA = 5   # segundos


def pasta_downloads() -> Path:
    """Pasta Downloads real (no Windows pode ter sido movida, ex.: para o OneDrive)."""
    if sys.platform == "win32":
        try:
            import winreg
            chave = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave) as k:
                valor, _ = winreg.QueryValueEx(k, "{374DE290-123F-4565-9164-39C4925E467B}")
            caminho = Path(winreg.ExpandEnvironmentStrings(valor))
            if caminho.is_dir():
                return caminho
        except OSError:
            pass
    return Path.home() / "Downloads"


def mover(origem: Path) -> list[Path]:
    """Move os briefings de `origem` para PASTA_SAIDA; devolve os destinos."""
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    movidos = []
    # Mais antigos primeiro: se houver "x.html" e "x (1).html", fica o mais recente.
    for arq in sorted(origem.iterdir(), key=lambda p: p.stat().st_mtime):
        m = RE_BRIEFING.match(arq.name)
        if not m or not arq.is_file():
            continue
        destino = PASTA_SAIDA / f"{m.group(1)}.{m.group(2).lower()}"
        try:
            shutil.move(str(arq), str(destino))     # substitui se já existir
        except OSError as e:                         # ainda sendo gravado pelo navegador
            print(f"⚠ {arq.name}: {e}")
            continue
        movidos.append(destino)
        print(f"✓ {arq.name} -> {destino}")
    return movidos


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vigiar", nargs="?", const=30, type=float, metavar="MIN",
                    help="fica esperando novos downloads por MIN minutos (padrão 30)")
    args = ap.parse_args()

    origem = pasta_downloads()
    print(f"Downloads: {origem}\nDestino:   {PASTA_SAIDA}")
    movidos = mover(origem)
    if args.vigiar is None:
        if not movidos:
            print("Nenhum briefing encontrado em Downloads.")
        return

    fim = time.time() + args.vigiar * 60
    print(f"Vigiando Downloads por {args.vigiar:g} min (Ctrl+C para parar)...")
    try:
        while time.time() < fim:
            time.sleep(INTERVALO_VIGIA)
            mover(origem)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
