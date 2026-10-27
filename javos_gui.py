"""
JAVOS GUI: Just Another Version for the Online Study
Interfaz gráfica de escritorio para Windows.
Soporte multi-idioma (ES, CA, EN), gestión de perfiles,
detección automática de assets de labJS y actualización en JATOS.
"""

import io
import os
import re
import sys
import threading
import zipfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import javos_core
import i18n

class JavosApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("880x820")
        self.minsize(820, 700)

        # Configuración de estilos
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self._configure_styles()

        # Gestor de configuración
        self.cfg_mgr = javos_core.ConfigManager()
        self.current_lang = self.cfg_mgr.data.get("language", "es")
        self.title(f"{i18n.get_text('app_title', self.current_lang)} - {i18n.get_text('app_subtitle', self.current_lang)}")

        self._build_ui()
        self._load_saved_profiles()
        self._apply_language(self.current_lang)

    def _t(self, key, **kwargs):
        return i18n.get_text(key, self.current_lang, **kwargs)

    def _configure_styles(self):
        bg_color = "#f4f6f9"
        card_bg = "#ffffff"
        primary_color = "#1f4b8e"
        primary_hover = "#163768"
        accent_color = "#27ae60"
        text_color = "#2c3e50"

        self.configure(bg=bg_color)
        self.style.configure(".", background=bg_color, foreground=text_color, font=("Segoe UI", 9))
        self.style.configure("TLabel", background=bg_color, font=("Segoe UI", 9))
        self.style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground=primary_color)
        self.style.configure("Subheader.TLabel", font=("Segoe UI", 9, "italic"), foreground="#7f8c8d")
        self.style.configure("Card.TLabelframe", background=card_bg, padding=12)
        self.style.configure("Card.TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground=primary_color, background=card_bg)
        
        self.style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), foreground="#ffffff", background=primary_color)
        self.style.map("Primary.TButton", background=[("active", primary_hover)])
        self.style.configure("Action.TButton", font=("Segoe UI", 11, "bold"), foreground="#ffffff", background=accent_color, padding=6)
        self.style.map("Action.TButton", background=[("active", "#1e8449")])

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding="15 10 15 10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Cabecera con Selector de Idioma y Selector de Perfil
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_box = ttk.Frame(header_frame)
        title_box.pack(side=tk.LEFT)
        self.lbl_head_title = ttk.Label(title_box, text=self._t("app_title"), style="Header.TLabel")
        self.lbl_head_title.pack(anchor=tk.W)
        self.lbl_head_sub = ttk.Label(title_box, text=self._t("app_subtitle"), style="Subheader.TLabel")
        self.lbl_head_sub.pack(anchor=tk.W)

        # Controles superiores derechos (Idioma y Perfil)
        top_right_box = ttk.Frame(header_frame)
        top_right_box.pack(side=tk.RIGHT, anchor=tk.E)

        # Selector de Idioma
        lang_sub = ttk.Frame(top_right_box)
        lang_sub.pack(fill=tk.X, pady=(0, 4))
        self.lbl_lang = ttk.Label(lang_sub, text=self._t("lang_label"))
        self.lbl_lang.pack(side=tk.LEFT, padx=5)
        self.lang_combo = ttk.Combobox(lang_sub, width=10, state="readonly", values=["Español", "Català", "English"])
        current_idx = 0 if self.current_lang == "es" else (1 if self.current_lang == "ca" else 2)
        self.lang_combo.current(current_idx)
        self.lang_combo.pack(side=tk.LEFT, padx=5)
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language_changed)

        # Selector de Perfil
        profile_sub = ttk.Frame(top_right_box)
        profile_sub.pack(fill=tk.X)
        self.lbl_prof = ttk.Label(profile_sub, text=self._t("profile_label"))
        self.lbl_prof.pack(side=tk.LEFT, padx=5)
        self.profile_combo = ttk.Combobox(profile_sub, width=16, state="readonly")
        self.profile_combo.pack(side=tk.LEFT, padx=5)
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_selected)

        self.btn_save_prof = ttk.Button(profile_sub, text=self._t("btn_save_profile"), command=self._save_current_profile)
        self.btn_save_prof.pack(side=tk.LEFT, padx=2)
        self.btn_del_prof = ttk.Button(profile_sub, text=self._t("btn_delete_profile"), command=self._delete_current_profile)
        self.btn_del_prof.pack(side=tk.LEFT, padx=2)

        # 2. Tarjeta 1: Servidor JATOS y Autenticación
        self.conn_card = ttk.LabelFrame(main_frame, text=self._t("sec1_title"), style="Card.TLabelframe")
        self.conn_card.pack(fill=tk.X, pady=(0, 8))

        # URL Servidor
        url_row = ttk.Frame(self.conn_card)
        url_row.pack(fill=tk.X, pady=3)
        self.lbl_url = ttk.Label(url_row, text=self._t("lbl_server_url"))
        self.lbl_url.pack(side=tk.LEFT, padx=(0, 8))
        self.ent_url = ttk.Entry(url_row)
        self.ent_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.ent_url.insert(0, javos_core.DEFAULT_SERVER_URL)

        # Modo de Autenticación
        auth_mode_row = ttk.Frame(self.conn_card)
        auth_mode_row.pack(fill=tk.X, pady=3)
        self.lbl_auth = ttk.Label(auth_mode_row, text=self._t("lbl_auth_mode"))
        self.lbl_auth.pack(side=tk.LEFT, padx=(0, 8))
        self.auth_mode_var = tk.StringVar(value="creds")
        self.rb_creds = ttk.Radiobutton(auth_mode_row, text=self._t("auth_creds"), variable=self.auth_mode_var, value="creds", command=self._toggle_auth_mode)
        self.rb_creds.pack(side=tk.LEFT, padx=8)
        self.rb_token = ttk.Radiobutton(auth_mode_row, text=self._t("auth_token"), variable=self.auth_mode_var, value="token", command=self._toggle_auth_mode)
        self.rb_token.pack(side=tk.LEFT, padx=8)

        # Campos Usuario / Contraseña
        self.creds_frame = ttk.Frame(self.conn_card)
        self.creds_frame.pack(fill=tk.X, pady=3)
        self.lbl_user = ttk.Label(self.creds_frame, text=self._t("lbl_user"))
        self.lbl_user.pack(side=tk.LEFT, padx=(0, 8))
        self.ent_user = ttk.Entry(self.creds_frame, width=22)
        self.ent_user.pack(side=tk.LEFT, padx=(0, 15))
        self.lbl_pass = ttk.Label(self.creds_frame, text=self._t("lbl_pass"))
        self.lbl_pass.pack(side=tk.LEFT, padx=(0, 8))
        self.ent_pass = ttk.Entry(self.creds_frame, show="•", width=22)
        self.ent_pass.pack(side=tk.LEFT, padx=(0, 8))

        # Campo Token
        self.token_frame = ttk.Frame(self.conn_card)
        self.lbl_token = ttk.Label(self.token_frame, text=self._t("lbl_token"))
        self.lbl_token.pack(side=tk.LEFT, padx=(0, 8))
        self.ent_token = ttk.Entry(self.token_frame)
        self.ent_token.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        # Botón Probar Conexión
        test_row = ttk.Frame(self.conn_card)
        test_row.pack(fill=tk.X, pady=(6, 0))
        self.btn_test = ttk.Button(test_row, text=self._t("btn_test_conn"), command=self._on_test_connection, style="Primary.TButton")
        self.btn_test.pack(side=tk.LEFT)
        self.lbl_status_conn = ttk.Label(test_row, text=self._t("status_disconnected"), foreground="#7f8c8d")
        self.lbl_status_conn.pack(side=tk.LEFT, padx=12)

        # 3. Tarjeta 2: Estudio Destino en JATOS
        self.study_card = ttk.LabelFrame(main_frame, text=self._t("sec2_title"), style="Card.TLabelframe")
        self.study_card.pack(fill=tk.X, pady=(0, 8))

        s_row1 = ttk.Frame(self.study_card)
        s_row1.pack(fill=tk.X, pady=3)
        self.lbl_study_id = ttk.Label(s_row1, text=self._t("lbl_study_id"))
        self.lbl_study_id.pack(side=tk.LEFT, padx=(0, 8))
        self.ent_study_id = ttk.Entry(s_row1, width=12)
        self.ent_study_id.pack(side=tk.LEFT, padx=(0, 20))
        
        self.lbl_study_assets = ttk.Label(s_row1, text=self._t("lbl_study_assets"))
        self.lbl_study_assets.pack(side=tk.LEFT, padx=(0, 8))
        self.ent_study_assets = ttk.Entry(s_row1)
        self.ent_study_assets.pack(side=tk.LEFT, fill=tk.X, expand=True)

        s_row2 = ttk.Frame(self.study_card)
        s_row2.pack(fill=tk.X, pady=3)
        self.lbl_study_uuid = ttk.Label(s_row2, text=self._t("lbl_study_uuid"))
        self.lbl_study_uuid.pack(side=tk.LEFT, padx=(0, 8))
        self.ent_study_uuid = ttk.Entry(s_row2)
        self.ent_study_uuid.pack(side=tk.LEFT, fill=tk.X, expand=True)

        s_hint_row = ttk.Frame(self.study_card)
        s_hint_row.pack(fill=tk.X, pady=(2, 0))
        self.lbl_hint_assets = ttk.Label(s_hint_row, text=self._t("hint_study_assets"), font=("Segoe UI", 8, "italic"), foreground="#7f8c8d")
        self.lbl_hint_assets.pack(side=tk.LEFT)

        # 4. Tarjeta 3: Nueva Tarea (LabJS Export)
        self.task_card = ttk.LabelFrame(main_frame, text=self._t("sec3_title"), style="Card.TLabelframe")
        self.task_card.pack(fill=tk.X, pady=(0, 8))

        file_row = ttk.Frame(self.task_card)
        file_row.pack(fill=tk.X, pady=3)
        self.lbl_zip_path = ttk.Label(file_row, text=self._t("lbl_zip_path"))
        self.lbl_zip_path.pack(side=tk.LEFT, padx=(0, 8))
        self.ent_zip_path = ttk.Entry(file_row)
        self.ent_zip_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.btn_browse = ttk.Button(file_row, text=self._t("btn_browse"), command=self._browse_zip)
        self.btn_browse.pack(side=tk.LEFT)

        title_row = ttk.Frame(self.task_card)
        title_row.pack(fill=tk.X, pady=3)
        self.lbl_comp_title = ttk.Label(title_row, text=self._t("lbl_comp_title"))
        self.lbl_comp_title.pack(side=tk.LEFT, padx=(0, 8))
        self.ent_comp_title = ttk.Entry(title_row)
        self.ent_comp_title.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Fila de subcarpeta de versión (vX)
        ver_row = ttk.Frame(self.task_card)
        ver_row.pack(fill=tk.X, pady=3)
        self.lbl_ver_dir = ttk.Label(ver_row, text=self._t("lbl_version_dir"))
        self.lbl_ver_dir.pack(side=tk.LEFT, padx=(0, 8))
        self.ent_ver_dir = ttk.Entry(ver_row, width=12)
        self.ent_ver_dir.pack(side=tk.LEFT, padx=(0, 10))
        self.ent_ver_dir.insert(0, "v1")
        self.lbl_hint_ver = ttk.Label(ver_row, text=self._t("hint_version_dir"), font=("Segoe UI", 8, "italic"), foreground="#7f8c8d")
        self.lbl_hint_ver.pack(side=tk.LEFT)

        opts_row = ttk.Frame(self.task_card)
        opts_row.pack(fill=tk.X, pady=(4, 0))
        self.var_keep_latest = tk.BooleanVar(value=True)
        self.chk_keep_latest = ttk.Checkbutton(opts_row, text=self._t("chk_keep_latest"), variable=self.var_keep_latest)
        self.chk_keep_latest.pack(side=tk.LEFT)

        # 5. Botón de Acción Principal
        btn_action_frame = ttk.Frame(main_frame)
        btn_action_frame.pack(fill=tk.X, pady=8)
        self.btn_upload = ttk.Button(
            btn_action_frame,
            text=self._t("btn_start_update"),
            command=self._on_start_update,
            style="Action.TButton"
        )
        self.btn_upload.pack(fill=tk.X, ipady=4)

        # 6. Consola de Registro en Vivo
        self.log_card = ttk.LabelFrame(main_frame, text=self._t("sec_logs_title"), style="Card.TLabelframe")
        self.log_card.pack(fill=tk.BOTH, expand=True)

        log_top = ttk.Frame(self.log_card)
        log_top.pack(fill=tk.X, pady=(0, 4))
        self.btn_clear_logs = ttk.Button(log_top, text=self._t("btn_clear_logs"), command=self._clear_logs)
        self.btn_clear_logs.pack(side=tk.RIGHT)

        self.txt_log = tk.Text(self.log_card, height=8, wrap=tk.WORD, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4", relief=tk.FLAT)
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(self.log_card, command=self.txt_log.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.config(yscrollcommand=sb.set)

        self._log(self._t("welcome_log"))

    def _on_language_changed(self, event=None):
        val = self.lang_combo.get()
        if "Catal" in val:
            new_lang = "ca"
        elif "Eng" in val:
            new_lang = "en"
        else:
            new_lang = "es"
        self._apply_language(new_lang)

    def _apply_language(self, lang_code):
        self.current_lang = lang_code
        javos_core.set_language(lang_code)
        self.cfg_mgr.data["language"] = lang_code
        self.cfg_mgr.save()

        self.title(f"{self._t('app_title')} - {self._t('app_subtitle')}")
        self.lbl_head_title.config(text=self._t("app_title"))
        self.lbl_head_sub.config(text=self._t("app_subtitle"))
        self.lbl_lang.config(text=self._t("lang_label"))
        self.lbl_prof.config(text=self._t("profile_label"))
        self.btn_save_prof.config(text=self._t("btn_save_profile"))
        self.btn_del_prof.config(text=self._t("btn_delete_profile"))

        self.conn_card.config(text=self._t("sec1_title"))
        self.lbl_url.config(text=self._t("lbl_server_url"))
        self.lbl_auth.config(text=self._t("lbl_auth_mode"))
        self.rb_creds.config(text=self._t("auth_creds"))
        self.rb_token.config(text=self._t("auth_token"))
        self.lbl_user.config(text=self._t("lbl_user"))
        self.lbl_pass.config(text=self._t("lbl_pass"))
        self.lbl_token.config(text=self._t("lbl_token"))
        self.btn_test.config(text=self._t("btn_test_conn"))

        self.study_card.config(text=self._t("sec2_title"))
        self.lbl_study_id.config(text=self._t("lbl_study_id"))
        self.lbl_study_assets.config(text=self._t("lbl_study_assets"))
        self.lbl_study_uuid.config(text=self._t("lbl_study_uuid"))
        self.lbl_hint_assets.config(text=self._t("hint_study_assets"))

        self.task_card.config(text=self._t("sec3_title"))
        self.lbl_zip_path.config(text=self._t("lbl_zip_path"))
        self.btn_browse.config(text=self._t("btn_browse"))
        self.lbl_comp_title.config(text=self._t("lbl_comp_title"))
        self.lbl_ver_dir.config(text=self._t("lbl_version_dir"))
        self.lbl_hint_ver.config(text=self._t("hint_version_dir"))
        self.chk_keep_latest.config(text=self._t("chk_keep_latest"))

        self.btn_upload.config(text=self._t("btn_start_update"))
        self.log_card.config(text=self._t("sec_logs_title"))
        self.btn_clear_logs.config(text=self._t("btn_clear_logs"))

    def _log(self, text, level="INFO"):
        prefix = f"[{level}] " if level != "INFO" else "• "
        self.txt_log.insert(tk.END, f"{prefix}{text}\n")
        self.txt_log.see(tk.END)

    def _clear_logs(self):
        self.txt_log.delete("1.0", tk.END)

    def _toggle_auth_mode(self):
        mode = self.auth_mode_var.get()
        if mode == "creds":
            self.token_frame.pack_forget()
            self.creds_frame.pack(fill=tk.X, pady=3)
        else:
            self.creds_frame.pack_forget()
            self.token_frame.pack(fill=tk.X, pady=3)

    def _browse_zip(self):
        filename = filedialog.askopenfilename(
            title="Seleccionar archivo .zip exportado de LabJS",
            filetypes=[("Archivos ZIP / JZIP", "*.zip;*.jzip"), ("Todos los archivos", "*.*")]
        )
        if filename:
            self.ent_zip_path.delete(0, tk.END)
            self.ent_zip_path.insert(0, filename)
            
            # Inspeccionar metadatos de labJS para autocompletar
            info, err = javos_core.inspect_labjs_zip(filename)
            if info:
                title = info.get("title", "")
                dir_name = info.get("dirName", "")
                comps = info.get("components", [])

                # Autocompletar Assets Dir si está vacío
                if not self.ent_study_assets.get().strip() and dir_name:
                    self.ent_study_assets.delete(0, tk.END)
                    self.ent_study_assets.insert(0, dir_name)

                # Sugerir título de componente {Nombre}{Version}
                base_title = title or "Tarea"
                current_ver = self.ent_ver_dir.get().strip() or "v1"
                sug_title = f"{base_title}_{current_ver}"
                self.ent_comp_title.delete(0, tk.END)
                self.ent_comp_title.insert(0, sug_title)

                self._log(self._t("zip_inspected", title=title, dirName=dir_name, count=len(comps)))
            else:
                base_name = os.path.splitext(os.path.basename(filename))[0]
                current_ver = self.ent_ver_dir.get().strip() or "v1"
                self.ent_comp_title.delete(0, tk.END)
                self.ent_comp_title.insert(0, f"{base_name}_{current_ver}")
                if err:
                    self._log(self._t("log_zip_warning", err=err), level="WARNING")

    def _get_client(self):
        url = self.ent_url.get().strip() or javos_core.DEFAULT_SERVER_URL
        mode = self.auth_mode_var.get()
        if mode == "token":
            token = self.ent_token.get().strip()
            return javos_core.JatosClient(url=url, api_token=token)
        else:
            user = self.ent_user.get().strip()
            pw = self.ent_pass.get()
            return javos_core.JatosClient(url=url, username=user, password=pw)

    def _on_test_connection(self):
        self.lbl_status_conn.config(text=self._t("status_connecting"), foreground="#f39c12")
        self.btn_test.config(state=tk.DISABLED)

        def worker():
            client = self._get_client()
            ok, msg = client.test_connection()
            def update_ui():
                self.btn_test.config(state=tk.NORMAL)
                if ok:
                    self.lbl_status_conn.config(text=self._t("status_connected"), foreground="#27ae60")
                    self._log(f"{self._t('status_connected')}: {msg}")
                else:
                    self.lbl_status_conn.config(text=self._t("status_conn_failed"), foreground="#c0392b")
                    self._log(f"{self._t('status_conn_failed')}: {msg}", level="ERROR")
            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _on_start_update(self):
        zip_path = self.ent_zip_path.get().strip()
        study_uuid = self.ent_study_uuid.get().strip()
        study_assets = self.ent_study_assets.get().strip()
        study_id = self.ent_study_id.get().strip()
        comp_title = self.ent_comp_title.get().strip()
        version_dir = self.ent_ver_dir.get().strip() or "v1"

        if not os.path.isfile(zip_path):
            messagebox.showerror("Error", self._t("err_no_zip"))
            return

        if not study_uuid:
            messagebox.showerror("Error", self._t("err_no_uuid"))
            return

        self.btn_upload.config(state=tk.DISABLED)
        self._log(self._t("log_start", uuid=study_uuid))

        def worker():
            try:
                # 1. Conectar y autenticar en JATOS
                client = self._get_client()
                self._log(self._t("log_auth"))
                ok_auth, msg_auth = client.test_connection()
                if not ok_auth:
                    raise Exception(self._t("err_connect", msg=msg_auth))

                # 2. Descargar estudio existente para mantener histórico de archivos y versiones
                existing_study_bytes = None
                if study_id:
                    self._log(self._t("log_checking_prev", id=study_id))
                    ok_exp, exp_data = client.export_study(study_id)
                    if ok_exp:
                        existing_study_bytes = exp_data
                        self._log(self._t("log_prev_downloaded"))
                    else:
                        self._log(self._t("log_prev_failed"), level="INFO")

                # 3. Reempaquetar con subcarpeta de versión y fusión acumulativa
                self._log(self._t("log_processing", v=version_dir))
                repackaged_bytes, jas_data, final_version_dir = javos_core.repackage_labjs_study(
                    zip_input=zip_path,
                    target_study_uuid=study_uuid,
                    target_dir_name=study_assets,
                    new_component_title=comp_title,
                    version_dir=version_dir,
                    component_active=True,
                    keep_only_latest=self.var_keep_latest.get(),
                    existing_study_zip=existing_study_bytes
                )
                
                final_dir = jas_data.get("data", jas_data).get("dirName", study_assets)
                if final_version_dir != version_dir:
                    self._log(self._t("log_ver_exists", req=version_dir, final=final_version_dir))
                if study_assets and final_dir != study_assets:
                    self._log(self._t("log_assets_server", final=final_dir, given=study_assets))
                self._log(self._t("log_repack_ready", size=len(repackaged_bytes), path=f"{final_dir}/{final_version_dir}"))

                # 4. Subir archivo a JATOS
                self._log(self._t("log_uploading"))
                upload_ok, upload_msg = client.upload_jzip(repackaged_bytes, filename=os.path.basename(zip_path))
                if not upload_ok:
                    raise Exception(self._t("err_upload", msg=upload_msg))

                self._log(f"{upload_msg}")

                # 5. Verificar en el servidor que la nueva versión está realmente subida y activa
                # (la desactivación de versiones previas ya viaja en el study.jas importado)
                if study_id:
                    self._log(self._t("log_verifying"))
                    new_comp = jas_data.get("data", jas_data)["componentList"][-1]
                    with zipfile.ZipFile(io.BytesIO(repackaged_bytes)) as rz:
                        new_html = rz.read(f"{final_dir}/{new_comp['htmlFilePath']}")
                    ok_ver, msg_ver = client.verify_uploaded_version(
                        study_id, new_comp["uuid"], new_comp["htmlFilePath"], new_html,
                        require_first_active=self.var_keep_latest.get())
                    if not ok_ver:
                        raise Exception(self._t("err_not_applied", msg=msg_ver))
                    self._log(msg_ver)
                else:
                    self._log(self._t("log_no_verify"), level="INFO")

                self._log(self._t("log_done", title=comp_title, v=final_version_dir))

                def on_success():
                    # Incrementar sugerencia para la siguiente versión (ej. v1 -> v2)
                    m = re.match(r"^v(\d+)$", final_version_dir)
                    if m:
                        next_num = int(m.group(1)) + 1
                        self.ent_ver_dir.delete(0, tk.END)
                        self.ent_ver_dir.insert(0, f"v{next_num}")
                        # También sugerir nuevo título
                        base_t = comp_title.rsplit("_v", 1)[0]
                        self.ent_comp_title.delete(0, tk.END)
                        self.ent_comp_title.insert(0, f"{base_t}_v{next_num}")
                    messagebox.showinfo(self._t("success_title"), self._t("success_msg"))

                self.after(0, on_success)

            except Exception as e:
                err_msg = str(e)
                self._log(f"ERROR: {err_msg}", level="ERROR")
                self.after(0, lambda: messagebox.showerror("Error", err_msg))

            finally:
                self.after(0, lambda: self.btn_upload.config(state=tk.NORMAL))

        threading.Thread(target=worker, daemon=True).start()

    def _load_saved_profiles(self):
        profiles = self.cfg_mgr.list_profiles()
        self.profile_combo["values"] = profiles
        if profiles:
            self.profile_combo.current(0)
            self._apply_profile(profiles[0])

    def _on_profile_selected(self, event=None):
        name = self.profile_combo.get()
        if name:
            self._apply_profile(name)

    def _apply_profile(self, name):
        p = self.cfg_mgr.get_profile(name)
        if not p:
            return
        self.ent_url.delete(0, tk.END)
        self.ent_url.insert(0, p.get("url", ""))

        auth_mode = p.get("auth_mode", "creds")
        self.auth_mode_var.set(auth_mode)
        self._toggle_auth_mode()

        if auth_mode == "token":
            self.ent_token.delete(0, tk.END)
            self.ent_token.insert(0, p.get("token", ""))
        else:
            self.ent_user.delete(0, tk.END)
            self.ent_user.insert(0, p.get("username", ""))

        self.ent_study_id.delete(0, tk.END)
        self.ent_study_id.insert(0, p.get("study_id", ""))

        self.ent_study_uuid.delete(0, tk.END)
        self.ent_study_uuid.insert(0, p.get("study_uuid", ""))

        self.ent_study_assets.delete(0, tk.END)
        self.ent_study_assets.insert(0, p.get("study_assets", ""))

        self._log(self._t("log_profile_loaded", name=name))

    def _save_current_profile(self):
        current_name = self.profile_combo.get().strip()
        from tkinter.simpledialog import askstring
        name = askstring(self._t("btn_save_profile"), self._t("prompt_profile_name"), initialvalue=current_name)
        if not name:
            return

        p_data = {
            "url": self.ent_url.get().strip(),
            "auth_mode": self.auth_mode_var.get(),
            "username": self.ent_user.get().strip(),
            "token": self.ent_token.get().strip(),
            "study_id": self.ent_study_id.get().strip(),
            "study_uuid": self.ent_study_uuid.get().strip(),
            "study_assets": self.ent_study_assets.get().strip()
        }
        self.cfg_mgr.save_profile(name, p_data)
        self._load_saved_profiles()
        self.profile_combo.set(name)
        msg = self._t("profile_saved", name=name)
        self._log(msg)
        messagebox.showinfo(self._t("btn_save_profile"), msg)

    def _delete_current_profile(self):
        name = self.profile_combo.get()
        if not name:
            return
        if messagebox.askyesno(self._t("btn_delete_profile"), self._t("confirm_delete_profile", name=name)):
            self.cfg_mgr.delete_profile(name)
            self._load_saved_profiles()
            self._log(self._t("profile_deleted", name=name))

if __name__ == "__main__":
    app = JavosApp()
    app.mainloop()
