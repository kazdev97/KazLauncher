# Explicación del Sistema de Actualizaciones - KazLauncher

## Cómo Funciona el Botón de Revisar Actualizaciones

### Ubicación
El botón de actualizaciones se encuentra en la **esquina inferior derecha** de la ventana principal, mostrando la versión actual del launcher (ej: "v1.2.2-beta"). Al hacer clic en este texto, se ejecuta la verificación de actualizaciones.

### Flujo de Funcionamiento

1. **Usuario hace clic en la versión** (línea 335 de `main_window.py`):
   ```python
   self.version_status_label.mousePressEvent = lambda event: self.check_for_updates(manual=True)
   ```

2. **Se ejecuta `check_for_updates()`** (líneas 1145-1154):
   - Verifica si ya hay una verificación en curso
   - Si es manual, actualiza el texto a "Buscando actualizaciones..."
   - Crea un `UpdateCheckWorker` (hilo separado)
   - Conecta las señales para manejar los resultados

3. **`UpdateCheckWorker` ejecuta la verificación** (líneas 47-65):
   - Hace una petición GET a la API de GitHub:
     ```python
     API_URL = "https://api.github.com/repos/krutoychel24/hru-hru-launcher/releases/latest"
     ```
   - Compara la versión más reciente (`tag_name`) con la versión actual (`APP_VERSION`)
   - Emite una señal según el resultado:
     - `update_found`: Si hay una nueva versión disponible
     - `up_to_date`: Si ya tienes la última versión
     - `error_occurred`: Si ocurre un error de red o de la API

4. **Manejo de Resultados**:
   - **Si hay actualización** (`on_update_found`, línea 1193):
     - Guarda la información de la versión
     - Cambia el color del texto a rojo (#ff5555)
     - Muestra un diálogo con los detalles de la actualización
   
   - **Si está actualizado** (`on_up_to_date`, línea 1200):
     - Cambia el texto a "Tienes la última versión"
     - Cambia el color a verde (#50fa7b)
     - Muestra un diálogo confirmando que está actualizado
   
   - **Si hay error** (`on_update_error`, línea 1206):
     - Cambia el texto a "Error al buscar actualizaciones"
     - Cambia el color a gris (#aaa)
     - Muestra un diálogo con el error

### Actualización Automática

El sistema también puede iniciar una actualización automática:

1. **Preparación del Actualizador** (`prepare_updater`, línea 1131):
   - Crea la carpeta en Documents/Kaz Studio/KazLauncher
   - Copia `updater.exe` desde el ejecutable compilado
   - Solo funciona cuando el launcher está compilado (no en modo desarrollo)

2. **Inicio del Proceso de Actualización** (`start_update_process`, línea 1177):
   - Construye la URL de descarga usando el template:
     ```python
     DOWNLOAD_URL_TEMPLATE = "https://github.com/krutoychel24/hru-hru-launcher/releases/download/{tag}/{filename}"
     ```
   - Ejecuta `updater.exe` como proceso separado
   - El actualizador descarga el nuevo ejecutable y reemplaza el antiguo
   - Cierra el launcher actual

### Configuración de la API

**IMPORTANTE**: Para que el sistema de actualizaciones funcione correctamente, necesitas:

1. **Actualizar las URLs de la API** en `main_window.py` (líneas 41-42):
   - Cambiar `API_URL` al repositorio de GitHub de KazLauncher
   - Cambiar `DOWNLOAD_URL_TEMPLATE` para que apunte al repositorio correcto

2. **Actualizar el nombre del ejecutable** en `start_update_process` (línea 1184):
   - Cambiar `"KazLauncher.exe"` por `"KazLauncher.exe"` (o el nombre que uses)

3. **Asegurar que el repositorio tenga releases**:
   - Las releases deben seguir el formato estándar de GitHub
   - El `tag_name` debe coincidir con el formato de versión (ej: "v1.2.3")
   - El archivo ejecutable debe estar adjunto como asset en la release

### Ejemplo de Configuración

```python
# En main_window.py
API_URL = "https://api.github.com/repos/TU_USUARIO/kaz-launcher/releases/latest"
DOWNLOAD_URL_TEMPLATE = "https://github.com/TU_USUARIO/kaz-launcher/releases/download/{tag}/{filename}"

# En start_update_process
download_url = DOWNLOAD_URL_TEMPLATE.format(tag=version, filename="KazLauncher.exe")
```

### Notas Adicionales

- El sistema funciona **solo cuando el launcher está compilado** (no en modo desarrollo)
- La verificación se hace en un hilo separado para no bloquear la interfaz
- El usuario puede cancelar la verificación si ya está en curso
- Los errores de red se manejan graciosamente sin crashear la aplicación
