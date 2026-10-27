import unittest
import io
import zipfile
import json
import os
from unittest.mock import patch, MagicMock

import javos_core

class TestJavosCore(unittest.TestCase):

    def test_normalize_url(self):
        # Fallback a URL genérica por defecto cuando no se indica URL
        client_def = javos_core.JatosClient()
        self.assertEqual(client_def.base_url, "https://jatos.example.org")

        client1 = javos_core.JatosClient("https://jatos.example.org/jatos/")
        self.assertEqual(client1.base_url, "https://jatos.example.org")

        client2 = javos_core.JatosClient("https://custom-server.org:8000")
        self.assertEqual(client2.base_url, "https://custom-server.org:8000")

    def test_repackage_labjs_zip(self):
        # Crear un zip simulado de exportación de labJS
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            mock_jas = {
                "title": "Old labJS Title",
                "description": "LabJS experiment",
                "dirName": "old_assets_dir",
                "uuid": "old-random-uuid-1111",
                "componentList": [
                    {
                        "title": "Old Component",
                        "htmlFilePath": "index.html",
                        "reloadable": True,
                        "uuid": "comp-old-uuid-9999",
                        "active": True
                    }
                ]
            }
            zf.writestr("study.jas", json.dumps(mock_jas))
            zf.writestr("old_assets_dir/index.html", "<html><body>LabJS Experiment</body></html>")
            zf.writestr("old_assets_dir/scripts/main.js", "console.log('test');")

        zip_buffer.seek(0)

        # Reempaquetar con JAVOS especificando UUID, carpeta de assets y subcarpeta de versión v1
        target_uuid = "target-uuid-2222-3333"
        target_dir = "target_assets_dir"
        target_title = "Tarea Modelo v1"

        repackaged_bytes, jas_data, ver_dir = javos_core.repackage_labjs_study(
            zip_input=zip_buffer,
            target_study_uuid=target_uuid,
            target_dir_name=target_dir,
            new_component_title=target_title,
            version_dir="v1",
            component_active=True
        )

        self.assertEqual(ver_dir, "v1")
        self.assertEqual(jas_data["data"]["uuid"], target_uuid)
        self.assertEqual(jas_data["data"]["dirName"], target_dir)
        self.assertEqual(len(jas_data["data"]["componentList"]), 1)
        self.assertEqual(jas_data["data"]["componentList"][0]["title"], target_title)
        self.assertEqual(jas_data["data"]["componentList"][0]["htmlFilePath"], "v1/index.html")
        self.assertTrue(jas_data["data"]["componentList"][0]["active"])

        # Inspeccionar el archivo zip generado
        repackaged_io = io.BytesIO(repackaged_bytes)
        with zipfile.ZipFile(repackaged_io, "r") as zf:
            names = zf.namelist()
            self.assertIn("study.jas", names)
            self.assertIn(f"{target_dir}/v1/index.html", names)
            self.assertIn(f"{target_dir}/v1/scripts/main.js", names)
            
            # Verificar preservación del contenido
            html_content = zf.read(f"{target_dir}/v1/index.html").decode("utf-8")
            self.assertIn("LabJS Experiment", html_content)

    def test_repackage_labjs_named_jas_and_nested_data(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            mock_jas = {
                "version": "3",
                "data": {
                    "uuid": "old-random-uuid-9999",
                    "title": "esqueleto",
                    "dirName": "esqueleto",
                    "componentList": [
                        {
                            "uuid": "comp-uuid-8888",
                            "title": "esqueleto",
                            "htmlFilePath": "index.html",
                            "active": True
                        }
                    ]
                }
            }
            zf.writestr("esqueleto.jas", json.dumps(mock_jas))
            zf.writestr("esqueleto/index.html", "<html><body>Esqueleto v2</body></html>")

        zip_buffer.seek(0)

        target_uuid = "f3b7c10d-a66f-170d-fb8b-cd28218b14b1"
        repackaged_bytes, jas_data, ver_dir = javos_core.repackage_labjs_study(
            zip_input=zip_buffer,
            target_study_uuid=target_uuid,
            target_dir_name="",
            new_component_title="Esqueleto v2.1",
            component_active=True
        )

        study_obj = jas_data.get("data", jas_data)
        self.assertEqual(study_obj["uuid"], target_uuid)
        self.assertEqual(study_obj["dirName"], "esqueleto")
        self.assertEqual(ver_dir, "v1")
        self.assertEqual(study_obj["componentList"][0]["title"], "Esqueleto v2.1")
        self.assertEqual(study_obj["componentList"][0]["htmlFilePath"], "v1/index.html")

        repackaged_io = io.BytesIO(repackaged_bytes)
        with zipfile.ZipFile(repackaged_io, "r") as zf:
            self.assertIn("study.jas", zf.namelist())
            self.assertIn("esqueleto/v1/index.html", zf.namelist())

    def test_repackage_cumulative_with_existing_study(self):
        # 1. Simular archivo existente en JATOS con v1
        exist_buffer = io.BytesIO()
        with zipfile.ZipFile(exist_buffer, "w", zipfile.ZIP_DEFLATED) as ezf:
            old_jas = {
                "version": "3",
                "data": {
                    "uuid": "study-uuid-original",
                    "title": "Estudio Multi-versión",
                    "dirName": "assets_originales",
                    "componentList": [
                        {
                            "uuid": "comp-uuid-v1",
                            "title": "Tarea v1",
                            "htmlFilePath": "v1/index.html",
                            "active": True
                        }
                    ]
                }
            }
            ezf.writestr("study.jas", json.dumps(old_jas))
            ezf.writestr("assets_originales/v1/index.html", "<html><body>Version 1</body></html>")

        # 2. Simular nuevo zip exportado desde labJS para v2
        new_buffer = io.BytesIO()
        with zipfile.ZipFile(new_buffer, "w", zipfile.ZIP_DEFLATED) as nzf:
            lab_jas = {
                "title": "labJS export",
                "dirName": "lab_dir",
                "componentList": [{"htmlFilePath": "index.html"}]
            }
            nzf.writestr("study.jas", json.dumps(lab_jas))
            nzf.writestr("lab_dir/index.html", "<html><body>Version 2</body></html>")

        # 3. Reempaquetar con fusión acumulativa en v2
        repack_bytes, jas_data, ver_dir = javos_core.repackage_labjs_study(
            zip_input=new_buffer.getvalue(),
            target_study_uuid="study-uuid-original",
            target_dir_name="assets_originales",
            new_component_title="Tarea v2",
            version_dir="v2",
            component_active=True,
            keep_only_latest=True,
            existing_study_zip=exist_buffer.getvalue()
        )

        self.assertEqual(ver_dir, "v2")
        study_obj = jas_data.get("data", jas_data)
        comps = study_obj["componentList"]
        self.assertEqual(len(comps), 2)

        # La versión 1 debe seguir existiendo pero desactivada (keep_only_latest=True)
        self.assertEqual(comps[0]["title"], "Tarea v1")
        self.assertEqual(comps[0]["htmlFilePath"], "v1/index.html")
        self.assertFalse(comps[0]["active"])

        # La versión 2 debe estar activa
        self.assertEqual(comps[1]["title"], "Tarea v2")
        self.assertEqual(comps[1]["htmlFilePath"], "v2/index.html")
        self.assertTrue(comps[1]["active"])

        # Inspeccionar que el zip contiene AMBOS archivos físicos HTML
        repack_io = io.BytesIO(repack_bytes)
        with zipfile.ZipFile(repack_io, "r") as zf:
            names = zf.namelist()
            self.assertIn("assets_originales/v1/index.html", names)
            self.assertIn("assets_originales/v2/index.html", names)
            self.assertIn("<body>Version 1</body>", zf.read("assets_originales/v1/index.html").decode())
            self.assertIn("<body>Version 2</body>", zf.read("assets_originales/v2/index.html").decode())

    def _make_existing_study(self, dir_name="assets_originales", versions=("v1",), extra_props=None):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            data = {
                "uuid": "study-uuid-original",
                "title": "Estudio Multi-versión",
                "dirName": dir_name,
                "componentList": [
                    {"uuid": f"comp-{v}", "title": f"Tarea {v}", "htmlFilePath": f"{v}/index.html", "active": True}
                    for v in versions
                ]
            }
            data.update(extra_props or {})
            zf.writestr("Estudio.jas", json.dumps({"version": "3", "data": data}))
            for v in versions:
                zf.writestr(f"{dir_name}/{v}/index.html", f"<html>{v} antigua</html>")
        return buf.getvalue()

    def _make_labjs_zip(self, html="<html>nueva</html>"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("study.jas", json.dumps({"title": "labJS", "dirName": "lab_dir",
                                                 "componentList": [{"htmlFilePath": "index.html"}]}))
            zf.writestr("lab_dir/index.html", html)
        return buf.getvalue()

    def test_repackage_reused_version_dir_picks_next_free(self):
        # Reutilizar 'v1' (p. ej. tras reiniciar la app) no debe duplicar entradas en el zip
        repack, jas, ver = javos_core.repackage_labjs_study(
            zip_input=self._make_labjs_zip(),
            target_study_uuid="study-uuid-original",
            version_dir="v1",
            existing_study_zip=self._make_existing_study(versions=("v1", "v2"))
        )
        self.assertEqual(ver, "v3")
        with zipfile.ZipFile(io.BytesIO(repack)) as zf:
            names = zf.namelist()
            self.assertEqual(len(names), len(set(names)), "El zip contiene entradas duplicadas")
            old_v1 = zf.read("assets_originales/v1/index.html").decode()
            self.assertIn("v1 antigua", old_v1)
            self.assertIn('<base href="v1/">', old_v1)  # versiones previas también ancladas a su carpeta
            self.assertIn("nueva", zf.read("assets_originales/v3/index.html").decode())
        self.assertEqual(jas["data"]["componentList"][-1]["htmlFilePath"], "v3/index.html")

    def test_repackage_custom_existing_version_dir_raises(self):
        with self.assertRaises(ValueError):
            javos_core.repackage_labjs_study(
                zip_input=self._make_labjs_zip(),
                target_study_uuid="study-uuid-original",
                version_dir="piloto",
                existing_study_zip=self._make_existing_study(versions=("piloto",))
            )

    def test_repackage_uses_server_dir_and_keeps_properties(self):
        # Una carpeta de assets distinta a la del servidor generaría dos carpetas raíz (JATOS lo rechaza)
        repack, jas, _ = javos_core.repackage_labjs_study(
            zip_input=self._make_labjs_zip(),
            target_study_uuid="study-uuid-original",
            target_dir_name="otra_carpeta",
            existing_study_zip=self._make_existing_study(extra_props={"linearStudy": True,
                                                                     "endRedirectUrl": "https://example.org/fin"})
        )
        self.assertEqual(jas["data"]["dirName"], "assets_originales")
        self.assertTrue(jas["data"]["linearStudy"])
        self.assertEqual(jas["data"]["endRedirectUrl"], "https://example.org/fin")
        with zipfile.ZipFile(io.BytesIO(repack)) as zf:
            roots = {n.split("/", 1)[0] for n in zf.namelist() if "/" in n}
            self.assertEqual(roots, {"assets_originales"})

    def test_repackage_uuid_mismatch_raises(self):
        with self.assertRaises(ValueError):
            javos_core.repackage_labjs_study(
                zip_input=self._make_labjs_zip(),
                target_study_uuid="otro-uuid",
                existing_study_zip=self._make_existing_study()
            )

    def test_component_html_resolves_inside_version_dir(self):
        # JATOS sirve el HTML en /publix/<run>/<comp>/start y las rutas /publix/<run>/<comp>/<x>
        # se leen de <dirName>/<x>: sin <base>, script.js se cargaría de la raíz (otra versión).
        from html.parser import HTMLParser
        from urllib.parse import urljoin
        labjs_html = ('<!doctype html><html><head><meta charset="utf-8">'
                      '<script src="jatos.js"></script><script src="lib/lab.js"></script>'
                      '<script src="script.js"></script><link rel="stylesheet" href="lib/lab.css">'
                      '</head><body></body></html>')
        repack, jas, ver = javos_core.repackage_labjs_study(
            zip_input=self._make_labjs_zip(html=labjs_html),
            target_study_uuid="study-uuid-original",
            existing_study_zip=self._make_existing_study()
        )
        html = zipfile.ZipFile(io.BytesIO(repack)).read(f"assets_originales/{ver}/index.html").decode()

        class Refs(HTMLParser):
            base, refs = None, []
            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if tag == "base":
                    self.base = a["href"]
                elif a.get("src") or a.get("href"):
                    self.refs.append(a.get("src") or a.get("href"))
        parser = Refs()
        parser.feed(html)

        page = "https://jatos.example.org/publix/RUN/COMP/start"
        base = urljoin(page, parser.base) if parser.base else page
        resolved = {r: urljoin(base, r) for r in parser.refs}
        prefix = "https://jatos.example.org/publix/RUN/COMP/"
        self.assertEqual(resolved["../jatos.js"], prefix + "jatos.js")
        self.assertEqual(resolved["script.js"], prefix + f"{ver}/script.js")
        self.assertEqual(resolved["lib/lab.js"], prefix + f"{ver}/lib/lab.js")
        self.assertEqual(resolved["lib/lab.css"], prefix + f"{ver}/lib/lab.css")

    @staticmethod
    def _resp(status, text="", json_data=None):
        r = MagicMock()
        r.status_code = status
        r.text = text
        if json_data is None:
            r.json.side_effect = ValueError("no json")
        else:
            r.json.return_value = json_data
        return r

    @patch("requests.Session.post")
    def test_upload_gui_sends_confirmation_body(self, mock_post):
        mock_post.side_effect = [
            self._resp(401),                                        # API no disponible con sesión
            self._resp(200, json_data={"studyExists": True}),       # /import/study
            self._resp(200, "14"),                                  # /import/studyConfirmed
        ]
        client = javos_core.JatosClient(url="https://jatos.example.org")
        ok, msg = client.upload_jzip(b"PK")
        self.assertTrue(ok)
        confirm_call = mock_post.call_args_list[2]
        self.assertIn("/jatos/import/studyConfirmed", confirm_call[0][0])
        body = confirm_call[1]["json"]
        self.assertFalse(body["keepProperties"])
        self.assertFalse(body["keepAssets"])

    @patch("requests.Session.post")
    def test_upload_reports_failed_confirmation(self, mock_post):
        mock_post.side_effect = [
            self._resp(401),
            self._resp(200, json_data={"studyExists": True}),
            self._resp(400, "Import of study failed"),
        ]
        client = javos_core.JatosClient(url="https://jatos.example.org")
        ok, _ = client.upload_jzip(b"PK")
        self.assertFalse(ok)

    @patch("requests.Session.post")
    def test_upload_reports_api_rejection(self, mock_post):
        mock_post.side_effect = [self._resp(400, "Unpacking ZIP archive failed")]
        client = javos_core.JatosClient(url="https://jatos.example.org", api_token="jap_x")
        ok, msg = client.upload_jzip(b"PK")
        self.assertFalse(ok)
        self.assertIn("Unpacking", msg)
        self.assertEqual(mock_post.call_count, 1)

    @patch("requests.Session.post")
    def test_upload_redirect_is_not_success(self, mock_post):
        mock_post.side_effect = [self._resp(401), self._resp(303)]
        client = javos_core.JatosClient(url="https://jatos.example.org")
        ok, _ = client.upload_jzip(b"PK")
        self.assertFalse(ok)

    def test_verify_uploaded_version(self):
        repack, jas, _ = javos_core.repackage_labjs_study(
            zip_input=self._make_labjs_zip(),
            target_study_uuid="study-uuid-original",
            existing_study_zip=self._make_existing_study()
        )
        new_comp = jas["data"]["componentList"][-1]
        with zipfile.ZipFile(io.BytesIO(repack)) as zf:
            new_html = zf.read(f"assets_originales/{new_comp['htmlFilePath']}")
        client = javos_core.JatosClient(url="https://jatos.example.org")

        # Servidor actualizado: verificación correcta
        with patch.object(client, "export_study", return_value=(True, repack)):
            ok, _ = client.verify_uploaded_version("1", new_comp["uuid"], new_comp["htmlFilePath"],
                                                   new_html)
            self.assertTrue(ok)

        # Servidor sin cambios (importación no aplicada): debe detectarse
        with patch.object(client, "export_study", return_value=(True, self._make_existing_study())):
            ok, _ = client.verify_uploaded_version("1", new_comp["uuid"], new_comp["htmlFilePath"],
                                                   new_html)
            self.assertFalse(ok)

    @patch("requests.Session.get")
    def test_test_connection_token_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_get.return_value = mock_response

        client = javos_core.JatosClient(
            url="https://jatos.example.org",
            api_token="jap_1234567890abcdef"
        )
        ok, msg = client.test_connection()
        self.assertTrue(ok)
        self.assertIn("correctamente", msg.lower())

    @patch("requests.Session.post")
    @patch("requests.Session.get")
    def test_login_credentials_success(self, mock_get, mock_post):
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.text = "<html><script>$.ajaxSetup({ headers: { 'Csrf-Token': 'test-token-xyz' } });</script></html>"
        mock_get.return_value = mock_get_resp

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.url = "https://jatos.example.org/jatos"
        mock_post.return_value = mock_post_resp

        client = javos_core.JatosClient(
            url="https://jatos.example.org",
            username="testuser",
            password="secretpassword"
        )
        ok, msg = client.login()
        self.assertTrue(ok)
        self.assertIn("éxito", msg.lower())
        self.assertEqual(client.csrf_token, "test-token-xyz")
        self.assertEqual(client.session.headers.get("Csrf-Token"), "test-token-xyz")
        mock_post.assert_called_once()
        self.assertIn("/jatos/signin/local", mock_post.call_args[0][0])

    def test_profile_manager(self):
        temp_cfg = "test_javos_config.json"
        if os.path.exists(temp_cfg):
            os.remove(temp_cfg)

        cfg_mgr = javos_core.ConfigManager(config_path=temp_cfg)
        self.assertEqual(cfg_mgr.list_profiles(), [])

        # Guardar perfil 1
        cfg_mgr.save_profile("Perfil_LabA", {
            "url": "https://jatos.example.org",
            "username": "investigador1",
            "study_id": "14",
            "study_uuid": "uuid-1111",
            "study_assets": "assets_lab_a"
        })

        # Guardar perfil 2
        cfg_mgr.save_profile("Perfil_LabB", {
            "url": "https://jatos.example.org",
            "username": "investigador2",
            "study_id": "25",
            "study_uuid": "uuid-2222",
            "study_assets": "assets_lab_b"
        })

        profiles = cfg_mgr.list_profiles()
        self.assertIn("Perfil_LabA", profiles)
        self.assertIn("Perfil_LabB", profiles)

        p1 = cfg_mgr.get_profile("Perfil_LabA")
        self.assertEqual(p1["username"], "investigador1")
        self.assertEqual(p1["study_id"], "14")

        # Limpieza
        if os.path.exists(temp_cfg):
            os.remove(temp_cfg)

    def test_dpapi_encryption(self):
        original = "jap_12345secret_token"
        encrypted = javos_core.encrypt_string(original)
        self.assertNotEqual(original, encrypted)
        self.assertTrue(encrypted.startswith("DPAPI:"))

        decrypted = javos_core.decrypt_string(encrypted)
        self.assertEqual(original, decrypted)

if __name__ == "__main__":
    unittest.main()
