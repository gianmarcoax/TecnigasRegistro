# Catálogo Odoo - Tecnigass

Este es un generador de catálogos interactivo en la web que se conecta con la API de Odoo v18 utilizando la biblioteca XML-RPC para extraer productos, imágenes y categorías en tiempo real.

## Requisitos
- **Para Python (servidor local rápido)**: Python 3.x (no requiere bibliotecas externas, usa las funciones nativas `xmlrpc.client`, `json` y `http.server`).
- **Para PHP (servidor web tradicional como Apache/Nginx)**: PHP 7+ con la extensión `xmlrpc` habilitada en `php.ini`.

## Estructura del Proyecto
- `server.py`: Servidor HTTP en Python y proxy que actúa como backend de consulta hacia Odoo.
- `api.php`: Alternativa de backend en PHP, cumple la misma función que `server.py` consumiendo XML-RPC.
- `index.html`: Interfaz principal del usuario y buscador visual.
- `catalog.html`: Vista detallada y generador del PDF del catálogo (A4 resposive).
- `.gitignore`: Archivos que deben ser omitidos en caso de subirse a un repositorio (ej. GitHub, GitLab o Bitbucket).

## Instalación y Ejecución

### Opción 1: Usando Python (Recomendado para pruebas o desarrollo local)
1. Abrir la terminal en la carpeta del proyecto.
2. Ejecutar el script (no requiere librerías adicionales de `pip`):
   ```bash
   python server.py
   ```
3. Abrir el navegador en `http://localhost:8080`.

### Opción 2: Usando PHP (Recomendado para producción / hosting tradicional)
1. Asegurarse que el servidor (ej. XAMPP, Nginx, Apache) tenga habilitado PHP y en específico la extensión `xmlrpc`.
2. Servir los archivos en una carpeta pública de tu servidor (`htdocs` o `www`).
3. Apuntar la URL frontend local hacia el `api.php` en caso se requiera hacer cambios en los `.html`.

## Credenciales de Odoo
Por seguridad, las credenciales no están quemadas en el código. Para usar el proyecto, **debes crear un archivo `config.json`**.
1. Copia el archivo `config.example.json` y renómbralo a `config.json`.
2. Completa el archivo `config.json` con tus credenciales:
   ```json
   {
     "ODOO_URL": "https://tecnigass.pe",
     "ODOO_DB": "db_tecnigas",
     "ODOO_USER": "coadmin@gmail.com",
     "ODOO_APIKEY": "0ae62c7a79728cccb1196a00f738565c931a2435"
   }
   ```
> **Nota de Seguridad**: El archivo `config.json` se encuentra ignorado en el archivo `.gitignore`, por lo que de forma predeterminada no será subido a tu repositorio.

## Uso del Buscador y Carrito
1. Al acceder a la web, el sistema solicitará a Odoo los productos disponibles.
2. Usa la barra de búsqueda para filtrar la información deseada.
3. Añade los productos al carrito mediante los controladores interactivos.
4. Genera e imprime el catálogo final en formato PDF (Tamaño A4).
