"""Exporta los notebooks a un PDF unico con markdown + figuras (sin codigo).

Pipeline:
    notebook.ipynb -> ejecutar con nbconvert --execute (outputs frescos) ->
    extraer celdas markdown + outputs image/png -> stripear "Proximos pasos" ->
    concatenar con saltos de capitulo -> render HTML con MathJax via CDN ->
    chrome headless --print-to-pdf

El codigo fuente NO aparece. Las graficas SI (vienen de los outputs).

Uso:
    python scripts/export_notebooks_pdf.py [output.pdf]
    python scripts/export_notebooks_pdf.py --no-execute  # usar outputs ya guardados

Salida default: notebooks_resumen.pdf en la raiz del repo.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import mistune

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_DIR = REPO_ROOT / "notebooks"

# Orden explicito (no glob — controlamos la secuencia)
NOTEBOOKS = [
    "01_inspect_run.ipynb",
    "02_inspect_muons.ipynb",
    "03_validation_reyna.ipynb",
    "04_muograma_fuego.ipynb",
    "05_muograma_dem_fuego.ipynb",
]

# Headers a partir de los cuales se descarta el resto de la celda. Capturamos
# secciones to-do / planificacion para que el PDF quede como narrativa cerrada.
DROP_FROM_HEADER = re.compile(
    r"^#{1,4}\s+.*?(?:"
    r"Pr[oó]ximos pasos|Pendientes|"
    r"Siguiente paso|Siguientes pasos|Next steps|"
    r"Conclusi[oó]n de la validaci[oó]n|"
    r"Si los tests pasan|Si no pasan"
    r").*$",
    re.MULTILINE | re.IGNORECASE,
)


def execute_notebook(nb_path: Path, output_dir: Path) -> Path:
    """Ejecuta el notebook y guarda la version con outputs en output_dir."""
    output_path = output_dir / nb_path.name
    cmd = [
        sys.executable.replace("python", "jupyter") if "anaconda" in sys.executable
        else shutil.which("jupyter") or "jupyter",
        "nbconvert",
        "--to", "notebook",
        "--execute",
        "--output", nb_path.name,
        "--output-dir", str(output_dir),
        str(nb_path),
    ]
    # Si python esta en un env conda, prefiero el jupyter del mismo env
    env_jupyter = Path(sys.executable).parent / "jupyter"
    if env_jupyter.exists():
        cmd[0] = str(env_jupyter)
    print(f"  Ejecutando {nb_path.name}...", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"Fallo ejecutar {nb_path.name}")
    return output_path


def extract_parts(nb_path: Path) -> list[tuple[str, str]]:
    """Devuelve una lista de ('md', markdown_text) y ('img', base64_png)
    siguiendo el orden natural de las celdas. Las celdas de codigo se omiten
    pero sus outputs de imagen se conservan."""
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    parts: list[tuple[str, str]] = []
    for cell in nb["cells"]:
        if cell["cell_type"] == "markdown":
            src = cell["source"]
            if isinstance(src, list):
                src = "".join(src)
            match = DROP_FROM_HEADER.search(src)
            if match:
                src = src[: match.start()].rstrip()
            if not src.strip() or src.strip() == "---":
                continue
            parts.append(("md", src))
        elif cell["cell_type"] == "code":
            for output in cell.get("outputs", []):
                data = output.get("data", {})
                if "image/png" in data:
                    img = data["image/png"]
                    if isinstance(img, list):
                        img = "".join(img)
                    parts.append(("img", img))
    return parts


CSS = """
@page { size: A4; margin: 2cm 2.2cm; }
body {
    font-family: Georgia, 'Times New Roman', serif;
    max-width: 750px;
    margin: 0 auto;
    line-height: 1.55;
    color: #1a1a1a;
    font-size: 11pt;
}
h1 {
    page-break-before: always;
    border-bottom: 2px solid #333;
    padding-bottom: 0.2em;
    font-size: 1.8em;
    margin-top: 0.5em;
}
h1:first-of-type { page-break-before: avoid; }
h2 {
    border-bottom: 1px solid #bbb;
    padding-bottom: 0.15em;
    margin-top: 1.6em;
    font-size: 1.35em;
}
h3 { margin-top: 1.2em; font-size: 1.12em; }
h4 { margin-top: 1em; font-size: 1.0em; color: #333; }
p { text-align: justify; }
code {
    background: #f3f3f3;
    padding: 0.05em 0.35em;
    border-radius: 3px;
    font-size: 0.92em;
    font-family: 'Menlo', 'Consolas', monospace;
}
pre {
    background: #f7f7f7;
    padding: 0.7em 1em;
    overflow-x: auto;
    border-left: 3px solid #888;
    font-size: 0.85em;
    font-family: 'Menlo', 'Consolas', monospace;
    line-height: 1.4;
}
pre code { background: transparent; padding: 0; font-size: inherit; }
table {
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 0.93em;
    page-break-inside: avoid;
}
th, td { border: 1px solid #999; padding: 0.35em 0.7em; vertical-align: top; }
th { background: #eee; text-align: left; }
blockquote { border-left: 3px solid #888; padding-left: 1em; color: #555; margin: 1em 0; }
ul, ol { padding-left: 1.6em; }
li { margin: 0.15em 0; }
hr { border: none; border-top: 1px solid #ccc; margin: 1.5em 0; }
figure {
    margin: 1.2em 0;
    text-align: center;
    page-break-inside: avoid;
}
figure img {
    max-width: 100%;
    height: auto;
    border: 1px solid #ddd;
    border-radius: 3px;
}
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Muografía Fuego — Resumen de notebooks</title>
<style>{css}</style>
<script>
window.MathJax = {{
  tex: {{
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
    processEscapes: true
  }},
  options: {{ enableMenu: false }}
}};
</script>
<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
</head>
<body>
{body}
</body>
</html>
"""


def render_html(parts_by_notebook: list[list[tuple[str, str]]], html_path: Path) -> None:
    md_parser = mistune.create_markdown(
        plugins=["table", "strikethrough", "url"],
        escape=False,
    )
    body_chunks: list[str] = []
    for i, parts in enumerate(parts_by_notebook):
        if i > 0:
            body_chunks.append('<hr/>')
        for kind, content in parts:
            if kind == "md":
                body_chunks.append(md_parser(content))
            elif kind == "img":
                body_chunks.append(
                    f'<figure><img src="data:image/png;base64,{content}" /></figure>'
                )
    html_path.write_text(
        HTML_TEMPLATE.format(css=CSS.strip(), body="\n".join(body_chunks)),
        encoding="utf-8",
    )


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")
    if chrome is None:
        raise RuntimeError("No se encontro google-chrome / chromium en PATH.")

    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            chrome,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            f"--user-data-dir={tmp}",
            f"--print-to-pdf={pdf_path}",
            "--no-pdf-header-footer",
            "--virtual-time-budget=20000",
            html_path.resolve().as_uri(),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            raise RuntimeError(f"chrome fallo (rc={result.returncode})")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output_pdf", nargs="?", default=str(REPO_ROOT / "notebooks_resumen.pdf"))
    p.add_argument("--no-execute", action="store_true",
                   help="Saltar la ejecucion: usar outputs ya guardados en los .ipynb")
    args = p.parse_args()
    output_pdf = Path(args.output_pdf)

    parts_per_nb: list[list[tuple[str, str]]] = []
    with tempfile.TemporaryDirectory() as exec_dir:
        exec_dir_path = Path(exec_dir)
        for name in NOTEBOOKS:
            nb_path = NOTEBOOK_DIR / name
            if not nb_path.exists():
                sys.stderr.write(f"WARNING: falta {nb_path}, saltado\n")
                continue
            if args.no_execute:
                target = nb_path
            else:
                target = execute_notebook(nb_path, exec_dir_path)
            parts = extract_parts(target)
            n_md = sum(1 for k, _ in parts if k == "md")
            n_img = sum(1 for k, _ in parts if k == "img")
            print(f"  {name}: {n_md} celdas markdown, {n_img} figuras")
            parts_per_nb.append(parts)

    html_path = REPO_ROOT / "notebooks_resumen.html"
    render_html(parts_per_nb, html_path)
    print(f"HTML intermedio: {html_path}")

    render_pdf(html_path, output_pdf)
    print(f"PDF generado:    {output_pdf}  ({output_pdf.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
