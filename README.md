<p align="center">
  <img src="https://raw.githubusercontent.com/git4sim/HA-Toniebox/main/logo.png" alt="HA-Toniebox Logo" width="160" />
</p>

<h1 align="center">HA-Toniebox</h1>

<p align="center">
  <strong>Unofficial Home Assistant Integration for Toniebox / Tonie Cloud</strong><br/>
  Vollständige Integration deiner Tonieboxen, Creative Tonies, Content Tonies und Content Discs in Home Assistant.
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
- 🎭 Jede **Content Tonie** (gekaufte Figur) als eigenes Gerät mit Status, aktiver Box, Serien-ID
- 💿 Jede **Content Disc** als eigenes Gerät mit Status und Haushalt-Sperr-Funktion
- 📻 Jede **Toniebox** als eigenes Gerät — zeigt die aktuell aufgelegte Figur mit Name und Cover
- 📊 **Sensoren** für Kapitelanzahl, Gesamtdauer, Firmware-Version, Online-Status, aktive Box
- 🔘 **Buttons** zum Sortieren (Titel / Dateiname / Datum), Leeren und Aktualisieren
- 🔴 **Binary Sensors** für Transcoding, Live-Modus, Haushalt-Lock, aktive Figur
- 🎛️ **Switches** für LED, Kapitel-Überspringen, Scrubbing, Offline-Modus, Haushalt-Sperren
- 🌐 **Select-Entities** für Sprache, LED-Level, Tap-Richtung, Alters-Modus
- ⚙️ **13 Services** für Automationen: sortieren, löschen, umbenennen, Tune aufspielen, Gutschein einlösen u.v.m.
- 🌍 **Übersetzungen** für Deutsch, Englisch, Französisch, Spanisch und Italienisch
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
├── Toniebox 1       →  Media Player · Switches · Sensoren · Buttons · Select
├── Toniebox 2       →  ...
├── Creative Tonie A →  Media Player · Kapitel · Dauer · Sort/Clear Buttons · Live/Privat Switch
├── Creative Tonie B →  ...
├── Content Tonie 1  →  Sensoren · Binary Sensors · Lock Switch
├── Content Tonie 2  →  ...
├── Content Disc 1   →  Sensoren · Binary Sensors · Lock Switch
└── Content Disc 2   →  ...
```

Jedes Gerät erscheint unter **Einstellungen → Geräte & Dienste → Toniebox** mit seinen eigenen Entities.

---

## Entities

### Haushalt (Hub-Gerät)

| Entity | Beschreibung |
|---|---|
| `sensor.<haushalt>_account` | Angemeldetes Konto (E-Mail) |
| `sensor.<haushalt>_creative_tonies` | Anzahl Creative Tonies |
| `sensor.<haushalt>_content_tonies` | Anzahl Content Tonies (gekaufte Figuren) |
| `sensor.<haushalt>_content_discs` | Anzahl Content Discs |
| `sensor.<haushalt>_tonieboxen` | Anzahl Tonieboxen |
| `sensor.<haushalt>_kinder` | Anzahl Kinder-Profile |
| `sensor.<haushalt>_mitglieder` | Anzahl Haushaltsmitglieder |
| `sensor.<haushalt>_benachrichtigungen` | Anzahl ungelesener Benachrichtigungen |
| `sensor.<haushalt>_offene_einladungen` | Ausstehende Einladungen |
| `button.<haushalt>_alle_aktualisieren` | Alle Daten vom Server neu laden |

### Pro Toniebox

| Entity | Beschreibung |
|---|---|
| `media_player.<toniebox>` | Aktuell aufgelegte Figur, Cover-Bild, Wiedergabe-Position |
| `switch.<toniebox>_kapitel_ueberspringen` | Kapitel-Überspringen per Tippen ein/aus |
| `switch.<toniebox>_vorspulen_zurueckspulen` | Scrubbing durch Kippen ein/aus |
| `switch.<toniebox>_offline_modus` | Offline-Modus (Anzeige) |
| `switch.<toniebox>_kippen_und_klopfen` | Beschleunigungssensor ein/aus (ältere Boxen) |
| `sensor.<toniebox>_firmware` | Aktuelle Firmware-Version |
| `sensor.<toniebox>_zuletzt_gesehen` | Zeitstempel der letzten Verbindung |
| `sensor.<toniebox>_online_status` | API Online-Status (connected / offline / unknown) |
| `sensor.<toniebox>_generation` | Modell-Generation (classic / rosered / tng) |
| `sensor.<toniebox>_features` | Unterstützte Funktionen |
| `sensor.<toniebox>_zeitzone` | Konfigurierte Zeitzone |
| `sensor.<toniebox>_einstellungen_uebertragen` | Einstellungen synchronisiert (ja/nein) |
| `sensor.<toniebox>_setup_wlan` | WLAN-SSID des Setup-Netzwerks |
| `sensor.<toniebox>_hinzugefuegt_am` | Registrierungsdatum |
| `sensor.<toniebox>_schlafenszeit_farbe` | Nachtlicht-Farbe (tng) |
| `binary_sensor.<toniebox>_online` | Toniebox zuletzt aktiv (Erreichbarkeit) |
| `binary_sensor.<toniebox>_led_aktiv` | LED-Status |
| `select.<toniebox>_led_level` | LED-Helligkeit |
| `select.<toniebox>_sprache` | Spracheinstellung |
| `select.<toniebox>_tap_richtung` | Tipp-Richtung |
| `select.<toniebox>_alters_modus` | Alters-Modus |
| `number.<toniebox>_max_lautstaerke` | Maximale Lautstärke |
| `number.<toniebox>_lightring_helligkeit` | Lichtring-Helligkeit |
| `button.<toniebox>_aktualisieren` | Gerät neu laden |
| `button.<toniebox>_werkseinstellungen` | Einstellungen zurücksetzen |

### Pro Creative Tonie

| Entity | Beschreibung |
|---|---|
| `media_player.<tonie>` | Hauptentität mit Cover-Bild und Kapitelübersicht |
| `sensor.<tonie>_kapitel` | Anzahl Kapitel (inkl. Kapitelliste als Attribut) |
| `sensor.<tonie>_gesamtdauer` | Gesamtspieldauer in Minuten |
| `sensor.<tonie>_freie_zeit` | Verbleibende freie Kapazität in Minuten (max. 90 min) |
| `sensor.<tonie>_transkodierung` | Transkodierungs-Status |
| `switch.<tonie>_privat` | Tonie für Gastmitglieder ausblenden |
| `switch.<tonie>_live` | Live-Modus aktivieren |
| `binary_sensor.<tonie>_wird_verarbeitet` | Transkodierung läuft |
| `binary_sensor.<tonie>_live` | Live-Status |
| `binary_sensor.<tonie>_privat` | Privat-Status |
| `button.<tonie>_alle_kapitel_loeschen` | Alle Kapitel entfernen |
| `button.<tonie>_nach_titel_sortieren` | Kapitel alphabetisch sortieren |
| `button.<tonie>_nach_dateiname_sortieren` | Kapitel nach Dateiname sortieren |
| `button.<tonie>_nach_datum_sortieren` | Kapitel nach Datum sortieren |
| `button.<tonie>_aktualisieren` | Tonie-Daten neu laden |
| `select.<tonie>_kapitel_sortieren` | Sortierart auswählen und anwenden |

### Pro Content Tonie (gekaufte Figur)

| Entity | Beschreibung |
|---|---|
| `sensor.<content_tonie>_aktuelle_box` | Name der Toniebox, auf der die Figur liegt |
| `sensor.<content_tonie>_kapitel` | Anzahl Kapitel |
| `sensor.<content_tonie>_gesamtdauer` | Gesamtspieldauer in Minuten |
| `sensor.<content_tonie>_serien_id` | Serien- / Sales-ID der Figur |
| `binary_sensor.<content_tonie>_gerade_aktiv` | Liegt gerade auf einer Toniebox |
| `binary_sensor.<content_tonie>_im_haushalt_gesperrt` | An diesen Haushalt gebunden |
| `binary_sensor.<content_tonie>_transkodierung_aktiv` | Transkodierung läuft |
| `switch.<content_tonie>_im_haushalt_sperren` | Figur an Haushalt binden / freigeben |
| `button.<content_tonie>_tune_entfernen` | Aktiven Tune entfernen |
| `select.<content_tonie>_sprache` | Sprache (mehrsprachige Figuren) |

### Pro Content Disc

| Entity | Beschreibung |
|---|---|
| `sensor.<disc>_aktuelle_box` | Name der Toniebox, auf der die Disc liegt |
| `sensor.<disc>_serien_id` | Serien- / Sales-ID der Disc |
| `binary_sensor.<disc>_gerade_aktiv` | Liegt gerade auf einer Toniebox |
| `binary_sensor.<disc>_im_haushalt_gesperrt` | An diesen Haushalt gebunden |
| `switch.<disc>_im_haushalt_sperren` | Disc an Haushalt binden / freigeben |

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

### `toniebox.move_chapter` — Kapitel verschieben

```yaml
service: toniebox.move_chapter
data:
  entity_id: media_player.mein_tonie
  chapter_id: "abc123"
  direction: up   # up | down
```

### `toniebox.upload_audio` — Audio hochladen

```yaml
service: toniebox.upload_audio
data:
  entity_id: media_player.mein_tonie
  file_path: /config/tonie_audio/geschichte.mp3
  title: "Meine Geschichte"   # optional
```

Unterstützte Formate: `mp3`, `ogg`, `wav`, `flac`, `m4a`, `aac`, `opus`.

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

### `toniebox.accept_invitation` / `toniebox.decline_invitation` — Einladung annehmen/ablehnen

```yaml
service: toniebox.accept_invitation
data:
  invitation_id: "einladungs-id"
```

---

## Automations-Beispiele

### Licht einschalten wenn Lieblings-Tonie aufgelegt wird

```yaml
automation:
  trigger:
    - platform: state
      entity_id: binary_sensor.benjamin_bluemchen_gerade_aktiv
      to: "on"
  action:
    - service: light.turn_on
      target:
        entity_id: light.kinderzimmer
```

### Benachrichtigung wenn Toniebox offline geht

```yaml
automation:
  trigger:
    - platform: state
      entity_id: binary_sensor.kinderzimmer_online
      to: "off"
      for: "00:05:00"
  action:
    - service: notify.mobile_app
      data:
        message: "Toniebox Kinderzimmer ist seit 5 Minuten offline."
```

---

## Dashboard-Beispiel

```yaml
type: vertical-stack
cards:
  - type: picture-entity
    entity: media_player.meine_toniebox
    show_name: true
    show_state: true
  - type: entities
    title: Creative Tonie
    entities:
      - sensor.mein_tonie_kapitel
      - sensor.mein_tonie_gesamtdauer
      - sensor.mein_tonie_freie_zeit
      - select.mein_tonie_kapitel_sortieren
  - type: horizontal-stack
    cards:
      - type: button
        entity: button.mein_tonie_alle_kapitel_loeschen
        name: "Leeren"
      - type: button
        entity: button.mein_tonie_nach_titel_sortieren
        name: "A–Z"
      - type: button
        entity: button.mein_tonie_aktualisieren
        name: "Aktualisieren"
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

> [!TIP]
> Debug-Logs sind besonders hilfreich wenn Content Tonies oder Content Discs nicht angezeigt werden — sie zeigen die exakten API-Antwortfelder und helfen beim Diagnosieren von Parsing-Problemen.

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
