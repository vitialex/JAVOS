# JAVOS: Just Another Version for the Online Study

[Castellano](#castellano) · [Català](#català) · [English](#english)

---

## Castellano

**JAVOS** es una herramienta de escritorio para Windows que actualiza una tarea de **labJS** dentro de un estudio que ya existe en **JATOS**, sin crear un estudio nuevo y conservando todas las versiones anteriores.

### Objetivo

Al exportar una tarea desde labJS a JATOS:

1. labJS genera un archivo `.zip` cuyo archivo de metadatos (`.jas`) lleva un identificador UUID nuevo y aleatorio.
2. Al importarlo, JATOS crea un estudio nuevo en lugar de actualizar el existente, y los enlaces de los participantes dejan de apuntar a la versión actual.
3. Mantener un único estudio con varias versiones obliga a editar archivos JSON a mano o a gestionar componentes inactivos uno por uno.

Con JAVOS basta con seleccionar el `.zip` recién descargado de labJS e indicar el estudio de destino. JAVOS añade la nueva versión como un componente más del mismo estudio, la deja activa y mantiene intactas las anteriores.

JAVOS funciona con exportaciones de labJS y, en general, con cualquier archivo de estudio de JATOS que incluya un `.jas`.

### Cómo funciona

En cada actualización, JAVOS sigue estos pasos:

1. **Descarga el estudio existente** desde el servidor de JATOS, con todos sus archivos y componentes.
2. **Aísla la nueva versión** en una subcarpeta propia dentro de la carpeta del estudio (`v1`, `v2`, `v3`...). Si la subcarpeta indicada ya existe, usa la siguiente libre para no sobrescribir ninguna versión anterior.
3. **Ancla las rutas del HTML a su subcarpeta.** JATOS sirve el HTML de cada componente desde una dirección propia (`/publix/.../start`), de modo que las rutas relativas (`script.js`, `lib/...`, `static/...`) se resolverían contra la raíz del estudio y cargarían los archivos de otra versión. JAVOS inserta `<base href="vN/">` en el HTML de cada versión para que cargue siempre sus propios archivos.
4. **Añade la versión como componente nuevo** y, si así se indica, desactiva las anteriores. JATOS ejecuta siempre el primer componente activo, que pasa a ser la nueva versión.
5. **Conserva las propiedades del estudio** (descripción, redirección final, tipo de estudio, etc.) y sube el estudio consolidado a JATOS.
6. **Verifica la subida.** Vuelve a descargar el estudio y comprueba que el componente nuevo existe, está activo, es el primero activo y que su HTML coincide con el subido. Si algo no cuadra, JAVOS muestra un error en lugar de dar la subida por buena.

Como medida de seguridad, JAVOS se detiene si el Study UUID indicado no coincide con el del estudio descargado del servidor.

### Requisitos y descarga

#### Requisitos

- Windows 10 u 11 (las credenciales se cifran con la API de protección de datos de Windows, DPAPI).
- Una cuenta en un servidor de JATOS y ser miembro del estudio que se quiere actualizar.
- Probado con JATOS versión 3.11.3.
- Solo para ejecutar desde el código: Python 3.10 o superior.

#### Opción 1: Descargar el ejecutable (recomendado)

1. Ir a la sección **Releases** del repositorio en GitHub.
2. Descargar `JAVOS.exe` de la versión más reciente.
3. Ejecutarlo con doble clic. No necesita instalar nada más.

#### Opción 2: Ejecutar desde el código (con Python instalado)

1. Instalar las dependencias: `pip install -r requirements.txt`.
2. Hacer doble clic en `run_javos.bat`.

#### Opción 3: Compilar el ejecutable

Hacer doble clic en `build_exe.bat`. El script instala PyInstaller, compila en la carpeta temporal del sistema (para evitar bloqueos de OneDrive o SharePoint) y deja `JAVOS.exe` en la carpeta del proyecto.

### Conexión con JATOS

JAVOS admite dos formas de conexión.

#### Método A: Usuario y contraseña

- Introducir el usuario (o correo) y la contraseña del servidor de JATOS.
- Con el selector de perfiles (esquina superior derecha) se pueden guardar varias configuraciones con nombres descriptivos y alternar entre ellas con un clic.
- Seguridad: la contraseña nunca se guarda en disco; solo se mantiene en memoria durante la sesión.

#### Método B: API Token de JATOS

1. Iniciar sesión en el servidor de JATOS desde el navegador.
2. Hacer clic en el nombre de usuario (esquina superior derecha) para abrir el perfil.
3. Abrir la sección de tokens de API y crear un token nuevo con un nombre descriptivo.
4. Copiar el token generado (empieza por `jap_`).
5. En JAVOS, elegir la modalidad API Token y pegarlo.

Seguridad: los tokens se guardan cifrados con DPAPI en la carpeta privada del usuario (`%APPDATA%/JAVOS/`). Solo el mismo usuario de Windows, en el mismo equipo, puede descifrarlos.

### Uso en cuatro pasos

1. **Servidor JATOS y autenticación**
    - Indicar la URL del servidor (por ejemplo, `https://jatos.example.org`).
    - Elegir el método de acceso (usuario y contraseña, o API Token).
    - Pulsar **Probar conexión**.
2. **Estudio de JATOS a actualizar**
    - Introducir el **Study ID** (numérico) y el **Study UUID** del estudio existente. Ambos aparecen en la página del estudio en JATOS: el ID en la dirección del navegador y el UUID en las propiedades del estudio.
    - El campo de carpeta de assets puede dejarse vacío: JAVOS usa siempre la carpeta del estudio en el servidor.
    - Guardar el perfil para reutilizar la configuración en otras sesiones.
3. **Nueva versión de la tarea**
    - Pulsar **Examinar...** y elegir el `.zip` exportado de labJS.
    - Escribir el título de la versión (por ejemplo, `Tarea v2.3`).
    - Indicar la subcarpeta de versión. Si ya existe en el servidor, JAVOS usa automáticamente la siguiente libre.
        - Cuidado: se puede cambiar el nombre, pero no se admiten puntos (`.`) como separador en este campo. Usar un punto (u otro carácter no admitido) dará como resultado un error en la subida.
    - Mantener marcada la opción **Mantener activa solo la última versión** para que los participantes nuevos ejecuten siempre la más reciente.
4. **Actualización del estudio en JATOS**
    - Pulsar **Actualizar versión en JATOS**.
    - Seguir el proceso en el registro de operaciones. La subida termina bien solo si aparece el mensaje *Verificado en el servidor*.

Consejo: al probar la tarea después de una actualización, usar una ventana privada del navegador o recargar con Ctrl+F5 para descartar archivos en caché y poder ver la versión actualizada.

### Pruebas

Las pruebas automáticas comprueban el reempaquetado, la conservación de versiones, la subida a JATOS (simulada) y el cifrado de credenciales:

```
python test_javos_core.py
```

### Licencia

JAVOS se distribuye bajo la licencia **PolyForm Noncommercial 1.0.0** (ver el archivo [`LICENSE`](LICENSE)). Se puede usar, copiar, modificar y compartir con fines no comerciales, incluida la investigación y la docencia en universidades y centros públicos de investigación, siempre que se mantenga el aviso de autoría y la licencia en cada copia u obra derivada. El uso comercial requiere permiso por escrito del autor.

El software se ofrece "tal cual", sin garantía de ningún tipo. Antes de usar una versión con participantes, conviene guardar una copia del estudio y comprobar la actualización.

JAVOS es un proyecto independiente, sin relación oficial con los desarrolladores de JATOS ni de labJS.

### Cómo citar

Si JAVOS se usa en un trabajo de investigación, se agradece citarlo así:

> Sanchez-Azanza, V. (2026). *JAVOS: Just Another Version for the Online Study* (versión 1.0.0) [Software]. https://github.com/vitialex/JAVOS

### Autor

Victor Sanchez-Azanza ([@vitialex](https://github.com/vitialex))

---

## Català

**JAVOS** és una eina d'escriptori per a Windows que actualitza una tasca de **labJS** dins d'un estudi que ja existeix a **JATOS**, sense crear un estudi nou i conservant totes les versions anteriors.

### Objectiu

En exportar una tasca des de labJS a JATOS:

1. labJS genera un arxiu `.zip` l'arxiu de metadades del qual (`.jas`) duu un identificador UUID nou i aleatori.
2. En importar-lo, JATOS crea un estudi nou en lloc d'actualitzar l'existent, i els enllaços dels participants deixen d'apuntar a la versió actual.
3. Mantenir un únic estudi amb diverses versions obliga a editar arxius JSON a mà o a gestionar components inactius un per un.

Amb JAVOS només cal seleccionar el `.zip` acabat de descarregar de labJS i indicar l'estudi de destinació. JAVOS afegeix la nova versió com un component més del mateix estudi, la deixa activa i manté intactes les anteriors.

JAVOS funciona amb exportacions de labJS i, en general, amb qualsevol arxiu d'estudi de JATOS que inclogui un `.jas`.

### Com funciona

A cada actualització, JAVOS segueix aquests passos:

1. **Descarrega l'estudi existent** des del servidor de JATOS, amb tots els seus arxius i components.
2. **Aïlla la nova versió** en una subcarpeta pròpia dins la carpeta de l'estudi (`v1`, `v2`, `v3`...). Si la subcarpeta indicada ja existeix, empra la següent lliure per no sobreescriure cap versió anterior.
3. **Ancora les rutes de l'HTML a la seva subcarpeta.** JATOS serveix l'HTML de cada component des d'una adreça pròpia (`/publix/.../start`), de manera que les rutes relatives (`script.js`, `lib/...`, `static/...`) es resoldrien contra l'arrel de l'estudi i carregarien els arxius d'una altra versió. JAVOS insereix `<base href="vN/">` a l'HTML de cada versió perquè carregui sempre els seus propis arxius.
4. **Afegeix la versió com a component nou** i, si així s'indica, desactiva les anteriors. JATOS executa sempre el primer component actiu, que passa a ser la nova versió.
5. **Conserva les propietats de l'estudi** (descripció, redirecció final, tipus d'estudi, etc.) i puja l'estudi consolidat a JATOS.
6. **Verifica la pujada.** Torna a descarregar l'estudi i comprova que el component nou existeix, està actiu, és el primer actiu i que el seu HTML coincideix amb el pujat. Si alguna cosa no quadra, JAVOS mostra un error en lloc de donar la pujada per bona.

Com a mesura de seguretat, JAVOS s'atura si l'Study UUID indicat no coincideix amb el de l'estudi descarregat del servidor.

### Requisits i descàrrega

#### Requisits

- Windows 10 o 11 (les credencials es xifren amb l'API de protecció de dades de Windows, DPAPI).
- Un compte en un servidor de JATOS i ser membre de l'estudi que es vol actualitzar.
- Provat amb JATOS versió 3.11.3.
- Només per executar des del codi: Python 3.10 o superior.

#### Opció 1: Descarregar l'executable (recomanat)

1. Anar a la secció **Releases** del repositori a GitHub.
2. Descarregar `JAVOS.exe` de la versió més recent.
3. Executar-lo amb doble clic. No cal instal·lar res més.

#### Opció 2: Executar des del codi (amb Python instal·lat)

1. Instal·lar les dependències: `pip install -r requirements.txt`.
2. Fer doble clic a `run_javos.bat`.

#### Opció 3: Compilar l'executable

Fer doble clic a `build_exe.bat`. L'script instal·la PyInstaller, compila a la carpeta temporal del sistema (per evitar bloquejos d'OneDrive o SharePoint) i deixa `JAVOS.exe` a la carpeta del projecte.

### Connexió amb JATOS

JAVOS admet dues formes de connexió.

#### Mètode A: Usuari i contrasenya

- Introduir l'usuari (o correu) i la contrasenya del servidor de JATOS.
- Amb el selector de perfils (cantonada superior dreta) es poden desar diverses configuracions amb noms descriptius i alternar entre elles amb un clic.
- Seguretat: la contrasenya mai no es desa al disc; només es manté en memòria durant la sessió.

#### Mètode B: API Token de JATOS

1. Iniciar sessió al servidor de JATOS des del navegador.
2. Fer clic al nom d'usuari (cantonada superior dreta) per obrir el perfil.
3. Obrir la secció de tokens d'API i crear un token nou amb un nom descriptiu.
4. Copiar el token generat (comença per `jap_`).
5. A JAVOS, triar la modalitat API Token i enganxar-lo.

Seguretat: els tokens es desen xifrats amb DPAPI a la carpeta privada de l'usuari (`%APPDATA%/JAVOS/`). Només el mateix usuari de Windows, al mateix equip, els pot desxifrar.

### Ús en quatre passes

1. **Servidor JATOS i autenticació**
    - Indicar l'URL del servidor (per exemple, `https://jatos.example.org`).
    - Triar el mètode d'accés (usuari i contrasenya, o API Token).
    - Pitjar **Provar connexió**.
2. **Estudi de JATOS que s'ha d'actualitzar**
    - Introduir l'**Study ID** (numèric) i l'**Study UUID** de l'estudi existent. Tots dos apareixen a la pàgina de l'estudi a JATOS: l'ID a l'adreça del navegador i l'UUID a les propietats de l'estudi.
    - El camp de carpeta d'assets es pot deixar buit: JAVOS empra sempre la carpeta de l'estudi al servidor.
    - Desar el perfil per reutilitzar la configuració en altres sessions.
3. **Nova versió de la tasca**
    - Pitjar **Explorar...** i triar el `.zip` exportat de labJS.
    - Escriure el títol de la versió (per exemple, `Tasca v2.3`).
    - Indicar la subcarpeta de versió. Si ja existeix al servidor, JAVOS empra automàticament la següent lliure.
        - Compte: es pot canviar el nom, però no s'admeten punts (`.`) com a separador en aquest camp. Emprar un punt (o un altre caràcter no admès) donarà com a resultat un error en la pujada.
    - Mantenir marcada l'opció **Mantenir activa només la darrera versió** perquè els participants nous executin sempre la més recent.
4. **Actualització de l'estudi a JATOS**
    - Pitjar **Actualitzar versió a JATOS**.
    - Seguir el procés al registre d'operacions. La pujada acaba bé només si apareix el missatge *Verificat al servidor*.

Consell: en provar la tasca després d'una actualització, emprar una finestra privada del navegador o recarregar amb Ctrl+F5 per descartar arxius en memòria cau i poder veure la versió actualitzada.

### Proves

Les proves automàtiques comproven el reempaquetament, la conservació de versions, la pujada a JATOS (simulada) i el xifratge de credencials:

```
python test_javos_core.py
```

### Llicència

JAVOS es distribueix sota la llicència **PolyForm Noncommercial 1.0.0** (vegeu l'arxiu [`LICENSE`](LICENSE)). Es pot emprar, copiar, modificar i compartir amb finalitats no comercials, inclosa la recerca i la docència a universitats i centres públics de recerca, sempre que es mantengui l'avís d'autoria i la llicència a cada còpia o obra derivada. L'ús comercial requereix permís per escrit de l'autor.

El programari s'ofereix "tal qual", sense cap garantia. Abans d'emprar una versió amb participants, convé desar una còpia de l'estudi i comprovar l'actualització.

JAVOS és un projecte independent, sense relació oficial amb els desenvolupadors de JATOS ni de labJS.

### Com citar

Si JAVOS s'empra en un treball de recerca, s'agraeix citar-lo així:

> Sanchez-Azanza, V. (2026). *JAVOS: Just Another Version for the Online Study* (versió 1.0.0) [Programari]. https://github.com/vitialex/JAVOS

### Autor

Victor Sanchez-Azanza ([@vitialex](https://github.com/vitialex))

---

## English

**JAVOS** is a Windows desktop tool that updates a **labJS** task inside a study that already exists in **JATOS**, without creating a new study and while keeping every earlier version.

### Purpose

When a task is exported from labJS to JATOS:

1. labJS produces a `.zip` file whose metadata file (`.jas`) carries a new, random UUID.
2. On import, JATOS creates a new study instead of updating the existing one, and participant links no longer point to the current version.
3. Keeping a single study with several versions means editing JSON files by hand or managing inactive components one by one.

With JAVOS, you simply select the `.zip` freshly downloaded from labJS and specify the target study. JAVOS adds the new version as another component of the same study, activates it and leaves the earlier ones untouched.

JAVOS works with labJS exports and, more generally, with any JATOS study archive that includes a `.jas` file.

### How it works

On each update, JAVOS follows these steps:

1. **Downloads the existing study** from the JATOS server, with all its files and components.
2. **Isolates the new version** in its own subfolder within the study folder (`v1`, `v2`, `v3`...). If the requested subfolder already exists, it uses the next free one so that no earlier version is overwritten.
3. **Anchors the HTML paths to their subfolder.** JATOS serves each component's HTML from its own address (`/publix/.../start`), so relative paths (`script.js`, `lib/...`, `static/...`) would resolve against the study root and load another version's files. JAVOS inserts `<base href="vN/">` into each version's HTML so that it always loads its own files.
4. **Adds the version as a new component** and, if requested, deactivates the earlier ones. JATOS always runs the first active component, which becomes the new version.
5. **Preserves the study properties** (description, end redirect, study type, etc.) and uploads the consolidated study to JATOS.
6. **Verifies the upload.** It downloads the study again and checks that the new component exists, is active, is the first active one, and that its HTML matches the uploaded file. If anything does not match, JAVOS reports an error rather than treating the upload as successful.

As a safeguard, JAVOS stops if the Study UUID provided does not match that of the study downloaded from the server.

### Requirements and download

#### Requirements

- Windows 10 or 11 (credentials are encrypted with the Windows Data Protection API, DPAPI).
- An account on a JATOS server, and membership of the study to be updated.
- Tested with JATOS version 3.11.3.
- Only for running from source: Python 3.10 or later.

#### Option 1: Download the executable (recommended)

1. Go to the **Releases** section of the GitHub repository.
2. Download `JAVOS.exe` from the latest release.
3. Double-click it to run. Nothing else needs installing.

#### Option 2: Run from source (with Python installed)

1. Install the dependencies: `pip install -r requirements.txt`.
2. Double-click `run_javos.bat`.

#### Option 3: Build the executable

Double-click `build_exe.bat`. The script installs PyInstaller, builds in the system temporary folder (to avoid OneDrive or SharePoint locks) and places `JAVOS.exe` in the project folder.

### Connecting to JATOS

JAVOS supports two connection methods.

#### Method A: Username and password

- Enter the JATOS server username (or email) and password.
- The profile selector (top-right corner) lets you save several configurations under descriptive names and switch between them with one click.
- Security: the password is never written to disk; it is held in memory only for the session.

#### Method B: JATOS API token

1. Sign in to the JATOS server in a web browser.
2. Click your username (top-right corner) to open your profile.
3. Open the API tokens section and create a new token with a descriptive name.
4. Copy the generated token (it starts with `jap_`).
5. In JAVOS, choose the API Token option and paste it.

Security: tokens are stored encrypted with DPAPI in the user's private folder (`%APPDATA%/JAVOS/`). Only the same Windows user, on the same machine, can decrypt them.

### Four-step workflow

1. **JATOS server and authentication**
    - Enter the server URL (for example, `https://jatos.example.org`).
    - Choose the access method (username and password, or API Token).
    - Click **Test connection**.
2. **JATOS study to update**
    - Enter the **Study ID** (numeric) and the **Study UUID** of the existing study. Both appear on the study's page in JATOS: the ID in the browser address bar and the UUID in the study properties.
    - The assets folder field may be left blank: JAVOS always uses the study's folder on the server.
    - Save the profile to reuse the settings in later sessions.
3. **New task version**
    - Click **Browse...** and choose the `.zip` exported from labJS.
    - Enter the version title (for example, `Task v2.3`).
    - Specify the version subfolder. If it already exists on the server, JAVOS automatically uses the next free one.
        - Note: the name can be changed, but full stops (`.`) are not accepted as separators in this field. Using a full stop (or another unsupported character) will cause the upload to fail.
    - Keep **Keep only the latest version active** ticked so that new participants always run the most recent one.
4. **Updating the study in JATOS**
    - Click **Update version in JATOS**.
    - Follow the progress in the operation log. The upload has succeeded only if the message *Verified on the server* appears.

Tip: when testing the task after an update, use a private browser window or reload with Ctrl+F5 to bypass cached files and see the updated version.

### Tests

The automated tests cover repackaging, version preservation, the upload to JATOS (simulated) and credential encryption:

```
python test_javos_core.py
```

### Licence

JAVOS is distributed under the **PolyForm Noncommercial 1.0.0** licence (see the [`LICENSE`](LICENSE) file). It may be used, copied, modified and shared for noncommercial purposes, including research and teaching at universities and public research institutions, provided that the copyright notice and the licence are kept with every copy or derived work. Commercial use requires the author's written permission.

The software is provided "as is", without warranty of any kind. Before using a version with participants, it is advisable to keep a backup of the study and to check the update.

JAVOS is an independent project with no official connection to the developers of JATOS or labJS.

### How to cite

If JAVOS is used in research, please cite it as follows:

> Sanchez-Azanza, V. (2026). *JAVOS: Just Another Version for the Online Study* (version 1.0.0) [Software]. https://github.com/vitialex/JAVOS

### Author

Victor Sanchez-Azanza ([@vitialex](https://github.com/vitialex))
