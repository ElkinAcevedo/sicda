# Scripts

Utilidades de línea de comandos del proyecto (por ejemplo: verificar el dataset descargado o exportar el modelo activo). Cada script documenta su uso con `--help`.

| Script | Uso |
| --- | --- |
| `configurar_entorno.sh` / `.ps1` | Crea `.venv` e instala las dependencias de Python y Node. |
| `empaquetar_modelos.sh [salida.zip]` | Empaqueta el modelo activo, los metadatos de los demás modelos y las particiones de validación y prueba para ejecutar SICDA en otra máquina sin entrenar. |
