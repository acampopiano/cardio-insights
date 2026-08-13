"""Ejecuta un notebook con nbclient y lo normaliza con nbformat (evita
errores de validación estricta de nbconvert por outputs sin metadata/name)."""
import sys
import nbformat
from nbclient import NotebookClient

path = sys.argv[1]
nb = nbformat.read(path, as_version=4)

# Normalizar: nbformat completa campos requeridos faltantes.
_, nb = nbformat.validator.normalize(nb)

client = NotebookClient(nb, timeout=240, kernel_name="python3")
client.execute()

nbformat.write(nb, path)
print("OK:", path)
