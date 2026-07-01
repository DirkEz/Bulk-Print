# Bulk Print voor Windows

Een eenvoudige Python desktopapplicatie om meerdere bestanden in vaste volgorde naar een gekozen Windows-printer te sturen.

Bedrijf: Deyvo  
Auteur: Dirk Schaafstra

Logo: Deyvo

## Ondersteunde bestanden

- PDF
- Word: `.doc`, `.docx`, `.rtf`
- Excel: `.xls`, `.xlsx`, `.xlsm`, `.csv`
- PowerPoint: `.ppt`, `.pptx`
- Afbeeldingen: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tif`, `.tiff`

## Vereisten

- Windows
- Python 3.11 of nieuwer
- Microsoft Office voor het printen van Word-, Excel- en PowerPoint-bestanden

PDF-bestanden worden zonder externe PDF-reader verwerkt. De applicatie gebruikt PyMuPDF om PDF-pagina's naar afbeeldingen te renderen en stuurt die via de Windows-printerdriver naar de gekozen printer.

## Installatie

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Starten vanuit de terminal

```powershell
python -m bulk_print
```

## Gebruik

1. Start de applicatie.
2. Kies een printer in de dropdown.
3. Open eventueel `Printerinstellingen` om de Windows-voorkeuren van de gekozen printer aan te passen.
4. Kies het aantal kopieën en de gewenste oriëntatie.
5. Voeg bestanden toe via de knop `Bestanden toevoegen` of sleep bestanden naar het venster.
6. Controleer de lijst en verwijder bestanden indien nodig.
7. Klik op `Print starten`.
8. Gebruik `Annuleren` om het proces na het huidige bestand te stoppen.

Bij fouten gaat de applicatie door met het volgende bestand. Na afloop verschijnt een overzicht van bestanden die niet naar de printer konden worden verzonden. De app bevestigt dat bestanden in de printerwachtrij zijn gezet; de printerdriver bepaalt daarna de fysieke afdruk.

## Updates

De applicatie toont linksonder de huidige versie en zoekt kort na het starten automatisch naar updates. Met `Updates zoeken` kun je handmatig controleren.

Standaard gebruikt de updatechecker GitHub Releases via:

```text
DirkEz/bulk-print
```

Voor een andere release-repository kun je deze omgevingsvariabelen zetten:

```powershell
$env:BULK_PRINT_UPDATE_REPO="eigenaar/repository"
$env:BULK_PRINT_UPDATE_INSTALLER_PREFIX="BulkPrint-Setup-v"
python -m bulk_print
```

Automatisch installeren werkt alleen wanneer de app als geïnstalleerde Windows `.exe` draait. Vanuit `python -m bulk_print` wordt de installer wel gedownload, maar niet automatisch gestart.

## Windows installer bouwen

De repository bevat een Inno Setup installer en een GitHub Actions workflow die automatisch een Windows installer bouwt.

### Lokaal bouwen

Installeer eerst Inno Setup en zorg dat `iscc.exe` in `PATH` staat. Bouw daarna de installer met:

```powershell
.\scripts\build_windows_installer.ps1 -Version 1.0.0
```

De installer komt in:

```text
dist\BulkPrint-Setup-v1.0.0.exe
```

### Autobuilds via GitHub Actions

De workflow staat in:

```text
.github\workflows\build-windows.yml
```

Bij een push naar `main` of handmatige `workflow_dispatch` doet hij dit:

- bepaalt automatisch de volgende patchversie op basis van `bulk_print/__init__.py` en tags zoals `v1.0.0`
- verhoogt de versie met `0.0.1`
- commit de nieuwe versie terug naar de repository met `[skip ci]`
- maakt een nieuwe tag voor die versie
- bouwt de app met PyInstaller
- maakt een Inno Setup installer
- uploadt de installer als artifact
- maakt een GitHub Release met de installer als asset

De installernaam is belangrijk voor automatische updates:

```text
BulkPrint-Setup-v<versie>.exe
```

De zichtbare appnaam in Windows blijft `Bulk Print`; de versie wordt alleen gebruikt voor updates, releases en de installerbestandsnaam.

### Optionele aparte update-repository

Als je updates via een aparte release-repository wilt aanbieden, stel dan in GitHub deze variabele en secret in:

```text
Repository variable: UPDATE_RELEASE_REPO = eigenaar/repository
Repository secret: TARGET_REPO_TOKEN = GitHub token met release-rechten op die repository
```

Tijdens de build wordt de updatechecker in de `.exe` automatisch ingesteld op `UPDATE_RELEASE_REPO`. Als deze variabele niet is ingesteld, gebruikt de app de releases van de bronrepository zelf.
