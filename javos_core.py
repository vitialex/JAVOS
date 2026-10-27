"""
JAVOS: Just Another Version for the Online Study
Motor de sincronización y cliente API/Web para JATOS.
Permite conectar con credenciales (usuario/contraseña) o API Token,
empaquetar tareas exportadas desde labJS / OSWeb y actualizar componentes
en estudios de JATOS manteniendo activa la versión deseada.
"""

import io
import json
import os
import re
import sys
import zipfile
import base64
import ctypes
from ctypes import wintypes
from urllib.parse import urlparse
import uuid
import requests
import i18n

DEFAULT_SERVER_URL = "https://jatos.example.org"

# Idioma de los mensajes que devuelve el núcleo (lo fija la interfaz)
LANG = "es"

def set_language(lang):
    global LANG
    LANG = lang

def _m(key, **kwargs):
    return i18n.get_text(key, LANG, **kwargs)

class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte))
    ]

def encrypt_string(plain_text: str) -> str:
    """Cifra una cadena usando Windows DPAPI (CryptProtectData)."""
    if not plain_text or sys.platform != "win32":
        return plain_text
    try:
        data = plain_text.encode("utf-8")
        blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_byte)))
        blob_out = DATA_BLOB()
        if ctypes.windll.crypt32.CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
            encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return "DPAPI:" + base64.b64encode(encrypted).decode("ascii")
    except Exception:
        pass
    return plain_text

def decrypt_string(cipher_text: str) -> str:
    """Descifra una cadena usando Windows DPAPI (CryptUnprotectData)."""
    if not cipher_text or not str(cipher_text).startswith("DPAPI:") or sys.platform != "win32":
        return cipher_text
    try:
        raw_b64 = cipher_text[6:]
        data = base64.b64decode(raw_b64)
        blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_byte)))
        blob_out = DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
            decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return decrypted.decode("utf-8")
    except Exception:
        pass
    return cipher_text

def get_default_config_path() -> str:
    """Devuelve la ruta privada de configuración en %APPDATA%/JAVOS/."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        cfg_dir = os.path.join(appdata, "JAVOS")
    else:
        cfg_dir = os.path.expanduser("~/.javos")
    os.makedirs(cfg_dir, exist_ok=True)
    return os.path.join(cfg_dir, "javos_config.json")

class JatosClient:
    def __init__(self, url=None, username=None, password=None, api_token=None):
        self.raw_url = url or DEFAULT_SERVER_URL
        self.base_url = self._normalize_url(self.raw_url)
        self.username = username
        self.password = password
        self.api_token = api_token
        self.session = requests.Session()
        self.is_authenticated = False
        self.auth_mode = "token" if api_token else "credentials"
        self.csrf_token = None

        if self.api_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_token}",
                "Accept": "application/json"
            })

    @staticmethod
    def _normalize_url(url):
        """Normaliza la URL eliminando barras finales y ajustando el path base."""
        if not url:
            return DEFAULT_SERVER_URL
        url = url.strip().rstrip("/")
        if url.endswith("/jatos"):
            url = url[:-6]
        return url

    def test_connection(self):
        """Prueba la conexión al servidor JATOS según el método configurado."""
        if self.api_token:
            # Intento de consulta a endpoint de API v1
            endpoints_to_try = [
                f"{self.base_url}/jatos/api/v1/admin/token",
                f"{self.base_url}/jatos/api/v1/studies",
                f"{self.base_url}/jatos/api/v1/admin/status",
            ]
            for ep in endpoints_to_try:
                try:
                    resp = self.session.get(ep, timeout=10)
                    if resp.status_code in (200, 204):
                        self.is_authenticated = True
                        return True, _m("core_token_ok")
                    if resp.status_code in (401, 403):
                        return False, _m("core_token_unauthorised", code=resp.status_code)
                except requests.RequestException:
                    continue

            # Fallback simple
            try:
                r = self.session.get(f"{self.base_url}/jatos", timeout=10)
                if r.status_code == 200:
                    return True, _m("core_server_reachable")
            except requests.RequestException as e:
                return False, _m("core_err_connecting", err=e)

            return False, _m("core_token_not_validated")
        else:
            return self.login()

    def login(self):
        """Inicia sesión en JATOS usando usuario y contraseña con cookies de sesión y token CSRF."""
        if not self.username or not self.password:
            return False, _m("core_creds_required")

        login_url = f"{self.base_url}/jatos/login"
        try:
            # 1. Obtener la página de login para cookies iniciales (PLAY_SESSION) y extraer token CSRF
            get_resp = self.session.get(login_url, timeout=12)
            if get_resp.status_code != 200:
                return False, _m("core_login_page_error", code=get_resp.status_code)

            csrf_token = None
            csrf_match = re.search(r"Csrf-Token['\"]?:\s*['\"]([^'\"]+)['\"]", get_resp.text)
            if csrf_match:
                csrf_token = csrf_match.group(1)
            elif "csrfToken" in self.session.cookies:
                csrf_token = self.session.cookies.get("csrfToken")

            self.csrf_token = csrf_token
            if csrf_token:
                self.session.headers.update({
                    "Csrf-Token": csrf_token,
                    "X-Requested-With": "XMLHttpRequest"
                })

            # 2. Enviar credenciales al endpoint de autenticación local
            auth_url = f"{self.base_url}/jatos/signin/local"
            login_data = {
                "username": self.username,
                "password": self.password
            }

            post_resp = self.session.post(auth_url, data=login_data, timeout=15, allow_redirects=True)
            
            # Si el endpoint signin/local da 404 (versiones muy antiguas de JATOS), probar fallback a /jatos/login
            if post_resp.status_code == 404:
                post_resp = self.session.post(login_url, data=login_data, timeout=15, allow_redirects=True)

            if post_resp.status_code in (200, 302, 303):
                text_lower = post_resp.text.lower()
                if "invalid user or password" in text_lower or "login failed" in text_lower or "signin failed" in text_lower:
                    return False, _m("core_bad_credentials")
                
                self.is_authenticated = True
                return True, _m("core_login_ok")
            elif post_resp.status_code == 401:
                return False, _m("core_bad_credentials")
            else:
                return False, _m("core_login_failed", code=post_resp.status_code)

        except requests.RequestException as e:
            return False, _m("core_login_conn_error", err=e)

    def get_study_details(self, study_id):
        """Obtiene las propiedades del estudio y sus componentes actuales."""
        # 1. Probar API v1
        api_url = f"{self.base_url}/jatos/api/v1/studies/{study_id}"
        try:
            r = self.session.get(api_url, timeout=10)
            if r.status_code == 200:
                return True, r.json()
        except requests.RequestException:
            pass

        # 2. Probar interfaz GUI si estamos en sesión
        gui_url = f"{self.base_url}/jatos/{study_id}/properties"
        try:
            r = self.session.get(gui_url, timeout=10)
            if r.status_code == 200:
                try:
                    return True, r.json()
                except ValueError:
                    return True, {"raw_html": r.text}
        except requests.RequestException as e:
            return False, _m("core_study_details_error", err=e)

        return False, _m("core_study_details_none", id=study_id)

    def export_study(self, study_id):
        """
        Descarga el archivo .jzip del estudio existente en JATOS si existe.
        Devuelve (True, bytes) o (False, error_msg).
        """
        if not study_id:
            return False, _m("core_no_study_id")

        # 1. Probar API v1
        api_url = f"{self.base_url}/jatos/api/v1/studies/{study_id}"
        try:
            r = self.session.get(api_url, timeout=35)
            if r.status_code == 200 and r.content[:4] == b"PK\x03\x04":
                return True, r.content
        except requests.RequestException:
            pass

        # 2. Probar rutas alternativas en GUI si estamos en sesión
        gui_urls = [
            f"{self.base_url}/jatos/study/{study_id}/export",
            f"{self.base_url}/jatos/{study_id}/export"
        ]
        for url in gui_urls:
            try:
                r_gui = self.session.get(url, timeout=35)
                if r_gui.status_code == 200 and r_gui.content[:4] == b"PK\x03\x04":
                    return True, r_gui.content
            except requests.RequestException:
                pass

        return False, _m("core_export_failed")

    def get_study_components_count(self, study_id):
        """Intenta obtener el número de componentes existentes en el estudio."""
        if not study_id:
            return 0
        try:
            r = self.session.get(f"{self.base_url}/jatos/{study_id}/componentsTableData", timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    return len(data)
                elif isinstance(data, dict) and "data" in data:
                    return len(data["data"])
        except Exception:
            pass
        return 0

    # Opciones de sobrescritura al importar un estudio existente: se reemplazan
    # propiedades/componentes y la carpeta de assets, conservando su nombre actual.
    # Se incluyen también las claves de versiones antiguas de JATOS (overwrite*).
    IMPORT_FLAGS = {
        "keepProperties": False,
        "keepAssets": False,
        "keepCurrentAssetsName": True,
        "renameAssets": True,
        "overwriteProperties": True,
        "overwriteDir": True,
        "keepCurrentDirName": True,
        "renameDir": True,
    }

    def upload_jzip(self, jzip_bytes, filename="study.jzip"):
        """
        Sube el archivo .jzip a JATOS para importar o actualizar el estudio.
        Solo devuelve éxito si el servidor confirma explícitamente la importación;
        las redirecciones (p. ej. a la página de login o de inicio) se tratan como error.
        """
        api_error = None

        # 1. API v1 (importa y confirma en una sola llamada)
        api_url = f"{self.base_url}/jatos/api/v1/study"
        api_params = {k: str(self.IMPORT_FLAGS[k]).lower()
                      for k in ("keepProperties", "keepAssets", "keepCurrentAssetsName", "renameAssets")}
        try:
            files = {"study": (filename, jzip_bytes, "application/zip")}
            r = self.session.post(api_url, params=api_params, files=files, timeout=60, allow_redirects=False)
            if r.status_code in (200, 201):
                return True, _m("core_upload_ok_api")
            api_error = f"API HTTP {r.status_code}: {r.text[:300]}"
            # Si la API existe y ha rechazado el archivo, el GUI fallará igual: informar del error real
            if r.status_code not in (301, 302, 303, 307, 308, 401, 403, 404, 405):
                return False, _m("core_import_rejected", detail=api_error)
        except requests.RequestException as e:
            api_error = f"API: {str(e)}"

        # 2. Importación vía GUI en dos pasos: /jatos/import/study + /jatos/import/studyConfirmed
        headers = {}
        if self.csrf_token:
            headers["Csrf-Token"] = self.csrf_token
        try:
            files = {"study": (filename, jzip_bytes, "application/zip")}
            r_gui = self.session.post(f"{self.base_url}/jatos/import/study", files=files,
                                      headers=headers, timeout=60, allow_redirects=False)
            if r_gui.status_code != 200:
                return False, _m("core_upload_http_error", code=r_gui.status_code,
                                  detail=f"{r_gui.text[:300]} | {api_error or ''}")
            try:
                import_info = r_gui.json()
            except ValueError:
                return False, _m("core_upload_not_json", detail=r_gui.text[:200])

            # Sin este cuerpo JSON JATOS responde 400 y NO aplica la importación
            r_conf = self.session.post(f"{self.base_url}/jatos/import/studyConfirmed",
                                       json=self.IMPORT_FLAGS, headers=headers,
                                       timeout=60, allow_redirects=False)
            if r_conf.status_code not in (200, 201):
                return False, _m("core_import_not_confirmed", code=r_conf.status_code, detail=r_conf.text[:300])

            if import_info.get("studyExists"):
                return True, _m("core_upload_ok_overwritten")
            return True, _m("core_upload_ok_new")
        except requests.RequestException as e:
            return False, _m("core_upload_net_error", err=e)

    def verify_uploaded_version(self, study_id, component_uuid, html_rel_path, expected_html,
                                require_first_active=True):
        """
        Descarga de nuevo el estudio del servidor y comprueba que el componente nuevo
        existe, está activo y que su HTML coincide con el que se acaba de subir.
        Con 'require_first_active' exige además que sea el primer componente activo,
        que es el que JATOS ejecuta al abrir un enlace del estudio.
        """
        ok, data = self.export_study(study_id)
        if not ok:
            return False, _m("core_verify_download_failed", detail=data)
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
            jas_name = _find_jas_file(zf)
            if not jas_name:
                return False, _m("core_verify_no_jas")
            study_obj = json.loads(zf.read(jas_name).decode("utf-8"))
            study_obj = study_obj.get("data", study_obj)
            comps = study_obj.get("componentList", [])
            comp = next((c for c in comps if c.get("uuid") == component_uuid), None)
            if comp is None:
                return False, _m("core_verify_comp_missing")
            if not comp.get("active", True):
                return False, _m("core_verify_comp_inactive")
            first_active = next((c for c in comps if c.get("active", True)), None)
            if require_first_active and first_active is not comp:
                return False, _m("core_verify_not_first", title=first_active.get("title"))
            remote_path = f"{study_obj.get('dirName', '')}/{html_rel_path}"
            names = {n.replace("\\", "/"): n for n in zf.namelist()}
            if remote_path not in names:
                return False, _m("core_verify_file_missing", path=remote_path)
            if zf.read(names[remote_path]) != expected_html:
                return False, _m("core_verify_file_mismatch", path=remote_path)
        if first_active is not comp:
            return True, _m("core_verify_ok_not_first")
        return True, _m("core_verify_ok")

    def set_component_active(self, study_id, component_id, active=True):
        """Activa o desactiva un componente específico en JATOS."""
        # 1. Probar API v1 PATCH/POST
        url_api = f"{self.base_url}/jatos/api/v1/studies/{study_id}/components/{component_id}"
        payload = {"active": active}
        try:
            r = self.session.patch(url_api, json=payload, timeout=10)
            if r.status_code in (200, 204):
                return True, f"Componente {component_id} actualizado (active={active})."
        except requests.RequestException:
            pass

        # 2. Probar GUI properties endpoint
        url_gui = f"{self.base_url}/jatos/study/{study_id}/component/{component_id}/properties"
        try:
            r_gui = self.session.post(url_gui, json=payload, timeout=10)
            if r_gui.status_code in (200, 204):
                return True, f"Componente {component_id} actualizado vía GUI (active={active})."
        except requests.RequestException as e:
            return False, f"No se pudo cambiar estado del componente: {str(e)}"

        return False, f"No se pudo actualizar estado del componente {component_id}."


def inspect_labjs_zip(zip_input):
    """
    Inspecciona un archivo zip de labJS y extrae metadatos clave:
    nombre del archivo .jas, título, dirName, UUID y lista de componentes.
    """
    if isinstance(zip_input, str):
        with open(zip_input, "rb") as f:
            raw_zip = f.read()
        in_io = io.BytesIO(raw_zip)
    elif isinstance(zip_input, bytes):
        in_io = io.BytesIO(zip_input)
    else:
        in_io = zip_input

    in_io.seek(0)
    with zipfile.ZipFile(in_io, "r") as in_zf:
        jas_filename = _find_jas_file(in_zf)
        if not jas_filename:
            return None, _m("core_no_jas_in_zip")

        jas_content = in_zf.read(jas_filename).decode("utf-8")
        jas_data = json.loads(jas_content)
        study_obj = jas_data.get("data", jas_data)

        info = {
            "jas_filename": jas_filename,
            "title": study_obj.get("title", ""),
            "dirName": study_obj.get("dirName", ""),
            "uuid": study_obj.get("uuid", ""),
            "components": [c.get("title", "") for c in study_obj.get("componentList", [])]
        }
        return info, None


def _find_jas_file(zf):
    """Busca de forma flexible cualquier archivo con extensión .jas dentro del zip."""
    namelist = zf.namelist()
    
    # 1. Priorizar archivos .jas en la raíz
    for name in namelist:
        norm = name.replace("\\", "/").strip()
        if "/" not in norm and norm.lower().endswith(".jas"):
            return name

    # 2. Buscar en cualquier nivel
    for name in namelist:
        norm = name.replace("\\", "/").strip()
        if norm.lower().endswith(".jas"):
            return name

    return None


def _anchor_html_to_version_dir(html, version_dir):
    """
    JATOS sirve el HTML de un componente en '/publix/<run>/<componente>/start', de modo que
    las rutas relativas (script.js, lib/..., static/...) se resuelven contra la RAÍZ de la
    carpeta de assets y no contra la subcarpeta de versión: se cargarían los archivos de otra
    versión. Se inserta '<base href="vN/">' para anclarlas a su subcarpeta. jatos.js construye
    sus URLs con window.location (no le afecta <base>), pero su <script> debe seguir apuntando
    a la raíz, que es donde JATOS lo sirve.
    """
    if re.search(rb"<base\b", html, re.I):
        return html
    html = re.sub(rb"""(<script\b[^>]*?\bsrc\s*=\s*["'])(?:\./)?(jatos(?:\.min)?\.js["'])""",
                  rb"\1../\2", html, flags=re.I)
    base_tag = b'<base href="' + version_dir.encode("utf-8") + b'/">'
    m = re.search(rb"<head\b[^>]*>", html, re.I) or re.search(rb"<html\b[^>]*>", html, re.I)
    if m:
        return html[:m.end()] + base_tag + html[m.end():]
    return base_tag + html


def repackage_labjs_study(
    zip_input,
    target_study_uuid,
    target_dir_name=None,
    new_component_title=None,
    version_dir=None,
    component_active=True,
    keep_only_latest=True,
    existing_study_zip=None
):
    """
    Toma un archivo .zip exportado desde labJS, aísla sus archivos en una subcarpeta
    de versión ('version_dir', por defecto v1, v2...), conserva todos los archivos y
    componentes de versiones anteriores (si se proporciona 'existing_study_zip'),
    y devuelve los bytes del nuevo archivo .jzip consolidado para JATOS.
    """
    if isinstance(zip_input, str):
        with open(zip_input, "rb") as f:
            raw_zip = f.read()
        in_io = io.BytesIO(raw_zip)
    elif isinstance(zip_input, bytes):
        in_io = io.BytesIO(zip_input)
    else:
        in_io = zip_input

    in_io.seek(0)
    with zipfile.ZipFile(in_io, "r") as in_zf:
        # 1. Localizar archivo .jas en el zip de labJS
        jas_filename = _find_jas_file(in_zf)
        if not jas_filename:
            raise ValueError(_m("core_no_jas_repackage"))

        jas_content = in_zf.read(jas_filename).decode("utf-8")
        labjs_jas_data = json.loads(jas_content)
        labjs_study_obj = labjs_jas_data.get("data", labjs_jas_data)
        labjs_old_dir = labjs_study_obj.get("dirName", "")

        # Extraer nombre del HTML principal de labJS (ej. index.html)
        labjs_comps = labjs_study_obj.get("componentList", [])
        orig_comp = labjs_comps[0] if labjs_comps else {}
        orig_html = orig_comp.get("htmlFilePath", "index.html")
        main_html_file = os.path.basename(orig_html.replace("\\", "/")) or "index.html"

        # 2. Inicializar contenedor de salida y procesar estudio existente si está disponible
        out_io = io.BytesIO()
        with zipfile.ZipFile(out_io, "w", zipfile.ZIP_DEFLATED) as out_zf:
            final_components = []
            existing_count = 0
            exist_study_obj = None
            exist_jas_version = "3"
            existing_subdirs = set()

            if existing_study_zip:
                # Leer y preservar todos los componentes y archivos existentes
                exist_io = io.BytesIO(existing_study_zip if isinstance(existing_study_zip, bytes) else existing_study_zip.read())
                with zipfile.ZipFile(exist_io, "r") as exist_zf:
                    exist_jas_name = _find_jas_file(exist_zf)
                    if exist_jas_name:
                        exist_jas_data = json.loads(exist_zf.read(exist_jas_name).decode("utf-8"))
                        exist_study_obj = exist_jas_data.get("data", exist_jas_data)
                        exist_jas_version = str(exist_jas_data.get("version", "3"))

                        exist_uuid = exist_study_obj.get("uuid")
                        if exist_uuid and target_study_uuid and exist_uuid != target_study_uuid:
                            raise ValueError(_m("core_uuid_mismatch", given=target_study_uuid, server=exist_uuid))

                        # La carpeta de assets debe ser la del estudio existente: JATOS rechaza
                        # archivos con más de una carpeta en la raíz.
                        target_dir_name = exist_study_obj.get("dirName") or target_dir_name

                        # Copiar componentes previos ajustando el estado activo según opción
                        for comp in exist_study_obj.get("componentList", []):
                            comp_copy = dict(comp)
                            if keep_only_latest:
                                comp_copy["active"] = False
                            final_components.append(comp_copy)

                        existing_count = len(final_components)

                    # Copiar los archivos físicos de versiones previas (solo los de la carpeta de assets)
                    exist_prefix = f"{target_dir_name.strip()}/" if target_dir_name else ""
                    # HTML de componentes en subcarpetas: anclar sus rutas relativas a su carpeta
                    versioned_html = {c.get("htmlFilePath", "").replace("\\", "/") for c in final_components}
                    versioned_html = {p for p in versioned_html if "/" in p}
                    for item in exist_zf.infolist():
                        norm_item_name = item.filename.replace("\\", "/").strip()
                        if norm_item_name.lower().endswith(".jas") or item.is_dir():
                            continue
                        if exist_prefix and not norm_item_name.startswith(exist_prefix):
                            continue
                        rel = norm_item_name[len(exist_prefix):]
                        if "/" in rel:
                            existing_subdirs.add(rel.split("/", 1)[0])
                        content = exist_zf.read(item.filename)
                        if rel in versioned_html:
                            content = _anchor_html_to_version_dir(content, rel.rsplit("/", 1)[0])
                        out_zf.writestr(norm_item_name, content)

            # 3. Determinar el nombre de la subcarpeta de versión ('vX')
            used_numbers = [int(m.group(1)) for m in (re.match(r"^v(\d+)$", d) for d in existing_subdirs) if m]
            next_free = f"v{max(used_numbers + [existing_count]) + 1}"

            # Limpiar nombre de subcarpeta para sistema de archivos (sin barras)
            clean_version_dir = re.sub(r"[^\w\-.]", "_", str(version_dir or "").strip().strip("/\\"))
            if not clean_version_dir:
                clean_version_dir = next_free
            elif clean_version_dir in existing_subdirs:
                # Reutilizar una carpeta existente duplicaría entradas en el zip (JATOS no puede
                # descomprimirlo) y rompería la versión anterior: se usa la siguiente libre.
                if re.match(r"^v\d+$", clean_version_dir):
                    clean_version_dir = next_free
                else:
                    raise ValueError(_m("core_version_dir_exists", name=clean_version_dir))

            # Resolver carpeta de assets final
            if not target_dir_name or not target_dir_name.strip():
                target_dir_name = labjs_old_dir or "assets"
            target_dir_name = target_dir_name.strip()

            # 4. Copiar archivos del nuevo labJS bajo su subcarpeta aislada
            for item in in_zf.infolist():
                norm_fn = item.filename.replace("\\", "/").strip()
                if norm_fn.lower().endswith(".jas") or item.is_dir():
                    continue

                content = in_zf.read(item.filename)
                rel_path = norm_fn

                # Quitar prefijo de carpeta previa si existe
                if labjs_old_dir and rel_path.startswith(f"{labjs_old_dir}/"):
                    rel_path = rel_path[len(labjs_old_dir) + 1:]
                elif "/" in rel_path:
                    parts = rel_path.split("/", 1)
                    if len(parts) == 2 and not parts[1].startswith("/"):
                        rel_path = parts[1]

                if rel_path == main_html_file:
                    content = _anchor_html_to_version_dir(content, clean_version_dir)

                # Construir nueva ruta aislada: {target_dir_name}/{version_dir}/{rel_path}
                new_path = f"{target_dir_name}/{clean_version_dir}/{rel_path}"
                out_zf.writestr(new_path, content)

            # 5. Crear y añadir el nuevo componente a la lista
            new_comp = {
                "title": new_component_title or _m("core_default_comp_title", v=clean_version_dir),
                "htmlFilePath": f"{clean_version_dir}/{main_html_file}",
                "reloadable": True,
                "active": bool(component_active),
                "uuid": str(uuid.uuid4())
            }
            final_components.append(new_comp)

            # 6. Construir metadatos finales para study.jas. Si hay estudio existente se parte
            # de sus propiedades (linearStudy, endRedirectUrl, batches...) para no perderlas al
            # sobrescribir.
            if exist_study_obj:
                final_data = dict(exist_study_obj)
            else:
                final_data = {
                    "title": labjs_study_obj.get("title", "Estudio"),
                    "description": labjs_study_obj.get("description", ""),
                }
            final_data.update({
                "uuid": target_study_uuid,
                "dirName": target_dir_name,
                "componentList": final_components
            })
            final_jas = {"version": exist_jas_version, "data": final_data}

            out_zf.writestr("study.jas", json.dumps(final_jas, indent=2))

    out_io.seek(0)
    return out_io.getvalue(), final_jas, clean_version_dir


class ConfigManager:
    """Gestiona el guardado y carga de perfiles y configuraciones privadas con cifrado DPAPI."""
    def __init__(self, config_path=None):
        self.config_path = config_path or get_default_config_path()
        self._migrate_local_config()
        self._load()

    def _migrate_local_config(self):
        """Migra automáticamente el archivo local javos_config.json si existe a %APPDATA%."""
        local_cfg = "javos_config.json"
        if not os.path.exists(self.config_path) and os.path.exists(local_cfg):
            try:
                import shutil
                shutil.copy2(local_cfg, self.config_path)
            except Exception:
                pass

    def _load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {"profiles": {}}
        else:
            self.data = {"profiles": {}}

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def list_profiles(self):
        return list(self.data.get("profiles", {}).keys())

    def get_profile(self, name):
        prof = dict(self.data.get("profiles", {}).get(name, {}))
        # Descifrar campos sensibles de forma transparente
        if "token" in prof and prof["token"]:
            prof["token"] = decrypt_string(prof["token"])
        if "password" in prof and prof["password"]:
            prof["password"] = decrypt_string(prof["password"])
        return prof

    def save_profile(self, name, profile_data):
        if "profiles" not in self.data:
            self.data["profiles"] = {}
        
        to_save = dict(profile_data)
        # Cifrar campos sensibles antes de guardar en disco
        if "token" in to_save and to_save["token"]:
            to_save["token"] = encrypt_string(to_save["token"])
        if "password" in to_save and to_save["password"]:
            to_save["password"] = encrypt_string(to_save["password"])

        self.data["profiles"][name] = to_save
        self.save()

    def delete_profile(self, name):
        if "profiles" in self.data and name in self.data["profiles"]:
            del self.data["profiles"][name]
            self.save()
            return True
        return False
