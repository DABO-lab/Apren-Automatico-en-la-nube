# Cómo empezar a trabajar en el proyecto

> Guía para que cualquier integrante del equipo clone el repositorio, monte el entorno y
> trabaje en su propia rama desde Visual Studio Code, en Windows.
>
> Los ejemplos usan la rama `Aprendizaje-yese`. Cambia ese nombre por el tuyo.

---

## Antes de empezar: qué necesitas instalado

Abre **PowerShell** (tecla Windows → escribe "PowerShell" → Enter) y verifica lo que ya
tienes:

```powershell
git --version
code --version
uv --version
```

Lo que falte, se instala así:

```powershell
winget install Git.Git
winget install Microsoft.VisualStudioCode
winget install astral-sh.uv
```

**Cierra PowerShell y ábrelo de nuevo** después de instalar algo, o los comandos nuevos
no aparecen.

No necesitas instalar Python: `uv` se encarga de bajar la versión que el proyecto pide
(la 3.11).

### Preséntate ante git (solo la primera vez en tu computador)

```powershell
git config --global user.name "Tu Nombre"
git config --global user.email "tu@correo.com"
```

Usa el mismo correo de tu cuenta de GitHub, para que los commits queden a tu nombre.

---

## Paso 1 — Clonar el repositorio

Ubícate donde quieras guardar el proyecto y clónalo:

```powershell
cd $HOME\Documents
git clone https://github.com/DABO-lab/Apren-Automatico-en-la-nube.git
cd Apren-Automatico-en-la-nube
```

Si te pide iniciar sesión, GitHub abrirá una ventana del navegador. Autoriza y listo.

---

## Paso 2 — Abrirlo en Visual Studio Code

```powershell
code .
```

El punto significa "esta carpeta". VS Code abre el proyecto completo.

La primera vez te va a sugerir instalar extensiones. **Acepta estas dos**, que son las
que necesitas:

- **Python** (de Microsoft)
- **Jupyter** (de Microsoft)

---

## Paso 3 — Crear tu rama

**Nunca trabajes directamente sobre `main`.** Cada quien tiene su rama, y el trabajo
entra a `main` por pull request.

```powershell
git switch main
git pull
git switch -c Aprendizaje-yese
```

Qué hace cada línea: la primera te para en `main`, la segunda trae lo último que hayan
subido las demás, y la tercera crea tu rama **desde ahí** y te cambia a ella. El orden
importa: si creas la rama sin haber hecho `pull`, arrancas desde una versión vieja.

Para confirmar dónde estás:

```powershell
git branch --show-current
```

Debe responder `Aprendizaje-yese`. Abajo a la izquierda en VS Code también aparece el
nombre de la rama.

---

## Paso 4 — Montar el entorno

```powershell
uv sync
uv run pre-commit install
```

`uv sync` baja Python 3.11 si no lo tienes, crea la carpeta `.venv` dentro del proyecto
e instala **las versiones exactas** que usamos las demás (están fijadas en `uv.lock`).
Eso es lo que garantiza que a todas nos funcione igual.

`pre-commit install` activa el revisor automático de estilo que corre en cada commit.

### Elige el intérprete en VS Code

Presiona `Ctrl + Shift + P`, escribe **"Python: Select Interpreter"** y elige el que
diga `.venv` y `3.11`. Sin esto, VS Code usa otro Python y nada funciona.

---

## Paso 5 — Conseguir los datos

**El archivo CSV no está en el repositorio** — pesa demasiado y los datos crudos no se
versionan. Pídele a Dubian el archivo `JC-202607-citibike-tripdata.csv` y guárdalo donde
quieras en tu computador (por ejemplo en `Documentos`).

Después, dile al proyecto dónde lo dejaste:

```powershell
$env:TRIPS_RAW_DATA = "C:\Users\TU-USUARIO\Documents\JC-202607-citibike-tripdata.csv"
```

⚠️ Esa línea **dura solo mientras esa ventana de PowerShell esté abierta**. Si cierras y
vuelves a abrir, hay que repetirla. Para dejarla fija de una vez:

```powershell
[Environment]::SetEnvironmentVariable("TRIPS_RAW_DATA", "C:\Users\TU-USUARIO\Documents\JC-202607-citibike-tripdata.csv", "User")
```

Con esta segunda opción hay que cerrar y volver a abrir PowerShell (y VS Code) para que
tome el cambio.

---

## Paso 6 — Comprobar que todo funciona

```powershell
uv run python -m trips.data.load
```

Debe imprimir la ficha técnica del archivo: 109.095 viajes, el rango de fechas y los
nulos por columna. Si sale un error de "no encuentro el archivo", revisa el paso 5.

Después, genera los datos limpios:

```powershell
uv run python -m trips.data.clean
```

Termina diciendo `Guardado en ...\data\processed\viajes_limpio.parquet`. Ese archivo
tampoco se sube al repositorio: cada quien lo genera en su máquina con este comando.

---

## Paso 7 — Abrir los notebooks

En el panel izquierdo de VS Code, entra a `notebooks/` y abre el que necesites:

- `01-carga-y-limpieza.ipynb` — qué problemas tenían los datos y cómo se arreglaron
- `02-eda.ipynb` — qué explica la duración de un viaje

Arriba a la derecha del notebook aparece un botón para **seleccionar el kernel**. Elige
el del `.venv` del proyecto (dice `apren-automatico-en-la-nube (3.11...)`). Luego
**Run All** para ejecutarlo completo.

> Antes de leer el código, léete `docs/guia-del-proyecto.md`. Explica qué hicimos y por
> qué cada decisión — te ahorra mucho tiempo.

---

## El día a día

### Antes de ponerte a trabajar

```powershell
git switch main
git pull
git switch Aprendizaje-yese
git merge main
```

Trae lo que hayan subido las demás a tu rama, para no quedarte atrás. **Hazlo antes de
empezar, no después de escribir código encima** — así los conflictos, si los hay, son
pequeños.

### Cuando termines algo

```powershell
git add .
git commit -m "feat: descripción de lo que hiciste"
git push -u origin Aprendizaje-yese
```

El `-u origin Aprendizaje-yese` solo hace falta **la primera vez**. Después basta con
`git push`.

Prefijos para los mensajes, según lo que hiciste: `feat:` algo nuevo, `fix:` una
corrección, `docs:` documentación, `chore:` mantenimiento.

### Cuando quieras que entre a `main`

Entra al repositorio en GitHub y abre un **pull request** de tu rama hacia `main`.
Escribe qué cambia y cómo probarlo. Alguien del equipo lo revisa y lo mergea.

---

## Cosas que van a pasar (y no son errores)

### El primer commit te lo rechaza

```
ruff format...........................................Failed
- files were modified by this hook
```

**Es normal.** El revisor de estilo encontró algo, lo arregló y detuvo el commit para
que revises. Simplemente repite:

```powershell
git add .
git commit -m "el mismo mensaje"
```

Esta vez pasa.

### "Una directiva de Control de aplicaciones bloqueó este archivo"

Windows bloquea archivos sin firma digital. Si te sale al importar pandas:

```powershell
Get-ChildItem .venv -Recurse -Include *.pyd,*.dll | Unblock-File
```

Si te sale al abrir Jupyter, ese no se arregla igual — trabaja los notebooks dentro de
VS Code, que no pasa por ese ejecutable.

### "Deletion of directory failed"

Sale al cambiar de rama con archivos abiertos. Responde `n`, cierra los notebooks en VS
Code y vuelve a intentar.

### El notebook aparece modificado sin que lo hayas tocado

Puede ser solo el guardado de VS Code. Míralo en el panel de control de código fuente
(el ícono de las ramitas): si el cambio no es tuyo de verdad, puedes descartarlo.

---

## Tres reglas del equipo

1. **`main` no se toca directo.** Todo entra por rama y pull request.
2. **Un notebook, una persona a la vez.** Los notebooks no se fusionan solos: si dos
   personas editan el mismo archivo, alguien pierde su trabajo. Avisen por el grupo
   antes de meterle mano a uno.
3. **Trae `main` a tu rama seguido.** Un merge pequeño cada día es fácil; uno grande
   después de una semana es un dolor de cabeza.

---

## Si algo se rompe

Copia el mensaje de error **completo** y compártelo en el grupo. Casi todos los errores
de esta guía ya nos pasaron y están resueltos arriba.

Y una cosa que nunca sobra: mientras no hayas hecho `git push`, tu trabajo está solo en
tu computador. Sube seguido.
