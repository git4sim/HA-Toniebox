<p align="center">
  <img src="https://raw.githubusercontent.com/git4sim/HA-Toniebox/main/logo.png" alt="HA-Toniebox Logo" width="160" />
</p>

<h1 align="center">HA-Toniebox</h1>

<p align="center">
  <strong>Unofficial Home Assistant Integration for Toniebox / Tonie Cloud</strong><br/>
  Vollständige Integration deiner Creative Tonies und Tonieboxen in Home Assistant.
</p>

<p align="center">
  <a href="https://github.com/hacs/integration">
    <img src="https://img.shields.io/badge/HACS-Custom-orange.svg?logo=home-assistant&logoColor=white" alt="HACS Custom"/>
  </a>
  <img src="https://img.shields.io/github/v/release/git4sim/HA-Toniebox?label=version&color=blue" alt="Version"/>
  <img src="https://img.shields.io/badge/HA-2023.1%2B-brightgreen?logo=home-assistant" alt="Home Assistant"/>
  <img src="https://img.shields.io/github/license/git4sim/HA-Toniebox?color=lightgrey" alt="MIT License"/>
  <img src="https://img.shields.io/badge/vibecoded-%F0%9F%A4%96-blueviolet" alt="Vibecoded"/>
</p>

---

> [!WARNING]
> **Disclaimer — Bitte vor der Nutzung lesen**
>
> Dieses Projekt steht in **keiner Verbindung zu Boxine GmbH** (Hersteller von Toniebox / tonies.de) und wird von diesen weder unterstützt noch empfohlen.
> Es nutzt die offizielle Tonie Cloud REST API, die **sich jederzeit ohne Ankündigung ändern kann**.
> Nutzung **auf eigene Gefahr**. Keine Garantie, kein Support durch Boxine.
>
> 🤖 Diese Integration wurde **vibecoded** — mit KI-Unterstützung ([Claude by Anthropic](https://anthropic.com)) entwickelt und gegen ein echtes Toniebox-Konto getestet.

---

## Features

- 🧸 Jede **Creative Tonie** als eigenes Gerät mit Media Player, Cover-Bild und Kapitelliste
- 📻 Jede **Toniebox** als eigenes Gerät — zeigt den aktuell aufgelegten Tonie
- 🔌 **LED** und **Lautstärkeerkennung** direkt über Switches steuerbar
- 📊 **Sensoren** für Kapitelanzahl, Gesamtdauer, Firmware-Version, letzten Online-Status
- 🔘 **Buttons** zum Sortieren (Titel / Dateiname / Datum) und Leeren der Kapitelliste
- 🔽 **Select-Entity** zur direkten Sortierauswahl
- 🔴 **Binary Sensors** für Transcoding-Status, Live-Modus, Online-Status
- ⚙️ **10 Services** für Automationen: sortieren, löschen, umbenennen, Tune aufspielen, Gutschein einlösen u.v.m.
- 🔐 Keycloak OpenID Connect Authentifizierung — selbe Zugangsdaten wie die Toniebox App
- 🛠️ Config Flow Setup — **kein YAML erforderlich**
- 📦 HACS-kompatibel

---

## Installation via HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=git4sim&repository=HA-Toniebox&category=integration)

> [!NOTE]
> Falls der Button nicht funktioniert: `https://github.com/git4sim/HA-Toniebox` in HACS manuell als Custom Repository vom Typ **Integration** hinzufügen, nach **Toniebox** suchen und herunterladen.

Nach dem Download Home Assistant neu starten.

### Manuelle Installation

Den Ordner `custom_components/toniebox/` aus dem [neuesten Release](https://github.com/git4sim/HA-Toniebox/releases/latest) in das HA-Konfigurationsverzeichnis kopieren:

```
/config/custom_components/toniebox/
```

Home Assistant neu starten.

---

## Einrichtung

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=toniebox)

> [!NOTE]
> Falls der Button nicht funktioniert: **Einstellungen → Geräte & Dienste → Integration hinzufügen** und nach **Toniebox** suchen.

E-Mail-Adresse und Passwort des Toniebox-Kontos eingeben (dieselben Zugangsdaten wie in der [Toniebox App](https://tonies.com) oder auf [my.tonies.com](https://my.tonies.com)).

---

## Gerätehierarchie

Die Integration erstellt eine logische Gerätehierarchie in Home Assistant:

```
Haushalt (Hub)
├── Toniebox 1  →  Media Player · LED Switch · Mute Switch · Firmware · Last Seen
├── Toniebox 2  →  ...
├── Creative Tonie A  →  Media Player · Kapitel · Dauer · Sort/Clear Buttons · Live/Privat Switch
└── Creative Tonie B  →  ...
```

Jedes Gerät erscheint unter **Einstellungen → Geräte & Dienste → Toniebox** mit seinen eigenen Entities. Über "Gruppieren nach Haushalt" in der Geräteliste werden alle Geräte übersichtlich dem jeweiligen Haushalt zugeordnet.

---

## Entities

### Haushalt (Hub-Gerät)

| Entity | Beschreibung |
|---|---|
| `sensor.<haushalt>_account` | Angemeldetes Konto (E-Mail) |
| `sensor.<haushalt>_creative_tonies` | Anzahl Creative Tonies |
| `sensor.<haushalt>_tonieboxen` | Anzahl Tonieboxen |
| `sensor.<haushalt>_kinder` | Anzahl Kinder-Profile |
| `sensor.<haushalt>_mitglieder` | Anzahl Haushaltsmitglieder |
| `sensor.<haushalt>_benachrichtigungen` | Anzahl ungelesener Benachrichtigungen |
| `sensor.<haushalt>_offene_einladungen` | Ausstehende Einladungen |
| `button.<haushalt>_alle_aktualisieren` | Alle Daten vom Server neu laden |

### Pro Toniebox

| Entity | Beschreibung |
|---|---|
| `media_player.<toniebox>` | Aktuell aufgelegter Tonie, Cover-Bild, Status |
| `switch.<toniebox>_led` | LED ein/aus |
| `switch.<toniebox>_lautstaerke_kabel_ignorieren` | Lautstärke-Kabel-Erkennung überspringen |
| `sensor.<toniebox>_firmware` | Aktuelle Firmware-Version |
| `sensor.<toniebox>_zuletzt_gesehen` | Zeitstempel der letzten Verbindung |
| `binary_sensor.<toniebox>_online` | Toniebox erreichbar ja/nein |
| `binary_sensor.<toniebox>_led_aktiv` | LED-Status (lesend) |
| `button.<toniebox>_aktualisieren` | Gerät neu laden |

### Pro Creative Tonie

| Entity | Beschreibung |
|---|---|
| `media_player.<tonie>` | Hauptentität mit Cover-Bild und Kapitelübersicht |
| `sensor.<tonie>_kapitel` | Anzahl Kapitel (inkl. Kapitelliste als Attribut) |
| `sensor.<tonie>_gesamtdauer` | Gesamtspieldauer in Minuten |
| `switch.<tonie>_privat` | Tonie für Gastmitglieder ausblenden |
| `switch.<tonie>_live` | Live-Modus aktivieren |
| `binary_sensor.<tonie>_wird_verarbeitet` | Transcoding läuft gerade |
| `binary_sensor.<tonie>_live` | Live-Status (lesend) |
| `binary_sensor.<tonie>_privat` | Privat-Status (lesend) |
| `button.<tonie>_alle_kapitel_loeschen` | Alle Kapitel entfernen |
| `button.<tonie>_nach_titel_sortieren` | Kapitel alphabetisch sortieren |
| `button.<tonie>_nach_dateiname_sortieren` | Kapitel nach Dateiname sortieren |
| `button.<tonie>_nach_datum_sortieren` | Kapitel nach Datum sortieren |
| `button.<tonie>_aktualisieren` | Tonie-Daten neu laden |
| `select.<tonie>_kapitel_sortieren` | Sortierart auswählen und anwenden |

---

## Services

### `toniebox.sort_chapters` — Kapitel sortieren

```yaml
service: toniebox.sort_chapters
data:
  entity_id: media_player.mein_tonie
  sort_by: title   # title | filename | date
```

### `toniebox.clear_chapters` — Alle Kapitel löschen

```yaml
service: toniebox.clear_chapters
data:
  entity_id: media_player.mein_tonie
```

### `toniebox.remove_chapter` — Einzelnes Kapitel löschen

```yaml
service: toniebox.remove_chapter
data:
  entity_id: media_player.mein_tonie
  chapter_id: "abc123"
```

> Die Kapitel-IDs stehen als Attribut `chapters` am Media Player oder Kapitel-Sensor.

### `toniebox.rename_tonie` — Tonie umbenennen

```yaml
service: toniebox.rename_tonie
data:
  entity_id: media_player.mein_tonie
  name: "Schlaf Tonie"
```

### `toniebox.rename_toniebox` — Toniebox umbenennen

```yaml
service: toniebox.rename_toniebox
data:
  entity_id: media_player.meine_toniebox
  name: "Kinderzimmer"
```

### `toniebox.redeem_content_token` — Content Token einlösen

```yaml
service: toniebox.redeem_content_token
data:
  entity_id: media_player.mein_tonie
  token: "TOKEN123"
```

### `toniebox.apply_tune` — Tune auf Tonie aufspielen

```yaml
service: toniebox.apply_tune
data:
  entity_id: media_player.mein_tonie
  tune_id: "tune-id-xyz"
```

### `toniebox.remove_tune` — Tune entfernen (Original wiederherstellen)

```yaml
service: toniebox.remove_tune
data:
  entity_id: media_player.mein_tonie
```

### `toniebox.redeem_voucher` — Gutscheincode einlösen

```yaml
service: toniebox.redeem_voucher
data:
  code: "GUTSCHEIN123"
```

### `toniebox.dismiss_all_notifications` — Alle Benachrichtigungen löschen

```yaml
service: toniebox.dismiss_all_notifications
```

---

## Dashboard-Beispiel

```yaml
type: vertical-stack
cards:
  - type: picture-entity
    entity: media_player.mein_tonie
    show_name: true
    show_state: true
  - type: entities
    entities:
      - sensor.mein_tonie_kapitel
      - sensor.mein_tonie_gesamtdauer
      - select.mein_tonie_kapitel_sortieren
  - type: horizontal-stack
    cards:
      - type: button
        entity: button.mein_tonie_alle_kapitel_loeschen
        name: "🗑 Leeren"
      - type: button
        entity: button.mein_tonie_nach_titel_sortieren
        name: "🔤 A–Z"
      - type: button
        entity: button.mein_tonie_aktualisieren
        name: "🔄 Aktualisieren"
```

---

## Debug Logging

```yaml
logger:
  default: info
  logs:
    custom_components.toniebox: debug
```

Oder über **Einstellungen → Geräte & Dienste → Toniebox → Debug-Protokollierung aktivieren**.

---

## 🤖 Über Vibecoding

Diese Integration wurde mit **KI-Pair-Programming** ([Claude by Anthropic](https://anthropic.com)) entwickelt. Architektur, Authentifizierungsflow und alle Plattformen wurden iterativ mit KI-Unterstützung erstellt und gegen ein echtes Toniebox-Konto getestet.

Das bedeutet: Es funktioniert — aber **Randfälle können vorkommen**. PRs, Bug Reports und Verbesserungen sind herzlich willkommen!

---

## Quellen & Attribution

| Quelle | Lizenz | Verwendung |
|---|---|---|
| [Wilhelmsson177/tonie-api](https://github.com/Wilhelmsson177/tonie-api) | MIT | API-Endpoint-Recherche, Python-Konzept |
| [maximilianvoss/toniebox-api](https://github.com/maximilianvoss/toniebox-api) | Apache-2.0 | Konkrete API-URLs aus `Constants.java` |
| [toniebox-reverse-engineering/teddycloud](https://github.com/toniebox-reverse-engineering/teddycloud) | GPL-3.0 | Keycloak SSO Flow Dokumentation |
| [api.tonie.cloud/v2/doc](https://api.tonie.cloud/v2/doc/) | — | Offizielle REST API Dokumentation |

> Die verwendeten Endpunkte sind Teil der offiziellen Tonie Cloud API. Es werden keine DRM-Schutzmaßnahmen oder Zugriffskontrollen umgangen. Die Integration nutzt dieselbe API wie die offizielle App.

---

## Legal

- Veröffentlicht unter der **[MIT-Lizenz](LICENSE)**
- **Nicht verbunden mit Boxine GmbH**
- Toniebox® und Tonies® sind eingetragene Marken der Boxine GmbH
- Nutzung gemäß den [Nutzungsbedingungen](https://tonies.com/terms) von Boxine

---

<p align="center">Made with 🧸 + 🤖 + ☕ &nbsp;|&nbsp; <a href="https://github.com/git4sim/HA-Toniebox/issues">Bug melden</a></p>
