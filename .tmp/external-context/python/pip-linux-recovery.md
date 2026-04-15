---
source: Python docs + pip docs + Python Packaging User Guide
library: Python
package: python
topic: pip missing on linux
fetched: 2026-04-15T00:00:00Z
official_docs: https://docs.python.org/3/library/ensurepip.html
---

# Resolver `/usr/bin/python3: No module named pip` en Linux

## Opción 1: usar `ensurepip` si existe

La documentación oficial de Python indica que `ensurepip` puede reinstalar o bootstrapear `pip` sin acceder a Internet.

```bash
python3 -m ensurepip --upgrade
```

Si quieres además el comando `pip` sin sufijo, Python documenta:

```bash
python3 -m ensurepip --default-pip --upgrade
```

Nota oficial: `ensurepip` es un módulo opcional; algunas distribuciones Linux lo eliminan.

## Opción 2: instalar el paquete del sistema si `ensurepip` no existe

La guía de PyPA recomienda usar el gestor de paquetes de la distribución cuando el Python del sistema viene modificado por el distribuidor.

Ejemplos habituales:

```bash
# Debian / Ubuntu
sudo apt update
sudo apt install python3-pip

# Fedora / RHEL modernos
sudo dnf install python3-pip

# openSUSE
sudo zypper install python3-pip

# Arch Linux
sudo pacman -S python-pip
```

En Debian/Ubuntu, la guía también menciona `python3-venv` como paquete habitual junto a `python3-pip`.

## Verificación posterior

```bash
python3 -m pip --version
python3 -m pip list
```

Si ambos comandos responden sin error, `pip` ya funciona para `python3`.

## Referencias breves

- Python `ensurepip`: instala `pip` y no usa Internet
- pip docs: `ensurepip` es uno de los métodos soportados oficialmente
- PyPA Linux guide: si tu distro quitó `ensurepip`, usa el paquete del sistema
