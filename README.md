<p align="center">
  <img src="https://raw.githubusercontent.com/git4sim/HA-Toniebox/main/logo.png" alt="HA-Toniebox Logo" width="160" />
</p>

<h1 align="center">HA-Toniebox</h1>

<p align="center">
  <strong>Unofficial Home Assistant Integration for Toniebox / Tonie Cloud</strong><br/>
  <em>Inoffizielle Home Assistant Integration für Toniebox / Tonie Cloud</em>
</p>

<p align="center">
  <a href="https://github.com/hacs/integration">
    <img src="https://img.shields.io/badge/HACS-Custom-orange.svg?logo=home-assistant&logoColor=white" alt="HACS Custom"/>
  </a>
  <img src="https://img.shields.io/github/v/release/git4sim/HA-Toniebox?label=version&color=blue" alt="Version"/>
  <img src="https://img.shields.io/badge/HA-2026.3%2B-brightgreen?logo=home-assistant" alt="Home Assistant"/>
  <img src="https://img.shields.io/github/license/git4sim/HA-Toniebox?color=lightgrey" alt="MIT License"/>
  <img src="https://img.shields.io/badge/vibecoded-%F0%9F%A4%96-blueviolet" alt="Vibecoded"/>
</p>

---

> [!WARNING]
> **Disclaimer — Please read before use / Bitte vor der Nutzung lesen**
>
> This project has **no affiliation with Boxine GmbH** (manufacturer of Toniebox / tonies.de) and is neither supported nor endorsed by them.
> It uses the official Tonie Cloud REST API, which **may change at any time without notice**.
> Use **at your own risk**. No warranty, no support from Boxine.
>
> *Dieses Projekt steht in **keiner Verbindung zu Boxine GmbH** und wird von diesen weder unterstützt noch empfohlen. Es nutzt die offizielle Tonie Cloud REST API, die **sich jederzeit ohne Ankündigung ändern kann**. Nutzung **auf eigene Gefahr**.*
>
> 🤖 This integration was **vibecoded** — developed with AI assistance ([Claude by Anthropic](https://anthropic.com)) and tested against a real Toniebox account.

---

<!-- ENGLISH -->
# 🇬🇧 English

## Features

- 🧸 Each **Creative Tonie** as its own device with media player, cover image and chapter list
- 📻 Each **Toniebox** as its own device — shows the currently placed figure with name and cover
- 📊 **Sensors** for chapter count, total duration, firmware version, online status, active box
- 🔘 **Buttons** to sort (title / filename / date), clear and refresh
- 🔴 **Binary Sensors** for transcoding, live mode, household lock, active figure
- 🎛️ **Switches** for LED, chapter skipping, scrubbing, offline mode, household lock
- 🌐 **Select entities** for language, LED level, tap direction, age mode
- ⚙️ **13 Services** for automations: sort, clear, rename, apply tune, redeem voucher and more
- 🌍 **Translations** for English, German, French, Spanish and Italian
- 🔐 Keycloak OpenID Connect authentication — same credentials as the Toniebox app
- 🛠️ Config Flow setup — **no YAML required**
- 📦 HACS compatible

---

## Installation via HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=git4sim&repository=HA-Toniebox&category=integration)

> [!NOTE]
> If the button does not work: add `https://github.com/git4sim/HA-Toniebox` manually in HACS as a Custom Repository of type **Integration**, search for **Toniebox** and download.

Restart Home Assistant after download.

### Manual Installation

Copy the `custom_components/toniebox/` folder from the [latest release](https://github.com/git4sim/HA-Toniebox/releases/latest) into your HA configuration directory:

```
/config/custom_components/toniebox/
```

Restart Home Assistant.

---

## Setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=toniebox)

> [!NOTE]
> If the button does not work: go to **Settings → Devices & Services → Add Integration** and search for **Toniebox**.

Enter the email address and password of your Toniebox account (the same credentials as in the [Toniebox app](https://tonies.com) or on [my.tonies.com](https://my.tonies.com)).

---

## Device Hierarchy

The integration creates a logical device hierarchy in Home Assistant:

```
Household (Hub)
├── Toniebox 1       →  Media Player · Switches · Sensors · Buttons · Select
├── Toniebox 2       →  ...
├── Creative Tonie A →  Media Player · Chapters · Duration · Sort/Clear Buttons · Live/Private Switch
└── Creative Tonie B →  ...
```

Each device appears under **Settings → Devices & Services → Toniebox** with its own entities.

---

## Entities

### Household (Hub device)

| Entity | Description |
|---|---|
| `sensor.<household>_account` | Logged-in account (email) |
| `sensor.<household>_creative_tonies` | Number of Creative Tonies |
| `sensor.<household>_tonieboxes` | Number of Tonieboxes |
| `sensor.<household>_children` | Number of child profiles |
| `sensor.<household>_members` | Number of household members |
| `sensor.<household>_notifications` | Number of unread notifications |
| `sensor.<household>_pending_invitations` | Pending invitations |
| `button.<household>_refresh_all` | Reload all data from server |

### Per Toniebox

| Entity | Description |
|---|---|
| `media_player.<toniebox>` | Currently placed figure, cover image, playback position |
| `switch.<toniebox>_skip_chapters` | Chapter skipping via tap on/off |
| `switch.<toniebox>_scrubbing` | Scrubbing by tilting on/off |
| `switch.<toniebox>_offline_mode` | Offline mode |
| `switch.<toniebox>_tilt_and_tap` | Accelerometer on/off (older boxes) |
| `sensor.<toniebox>_firmware` | Current firmware version |
| `sensor.<toniebox>_last_seen` | Timestamp of last connection |
| `sensor.<toniebox>_online_status` | API online status (connected / offline / unknown) |
| `sensor.<toniebox>_generation` | Model generation (classic / rosered / tng) |
| `sensor.<toniebox>_features` | Supported features |
| `sensor.<toniebox>_timezone` | Configured timezone |
| `sensor.<toniebox>_setup_wifi` | SSID of setup network |
| `sensor.<toniebox>_added_at` | Registration date |
| `sensor.<toniebox>_bedtime_color` | Night light color (tng) |
| `binary_sensor.<toniebox>_online` | Toniebox recently active (reachability) |
| `binary_sensor.<toniebox>_led_active` | LED status |
| `select.<toniebox>_led_level` | LED brightness |
| `select.<toniebox>_language` | Language setting |
| `select.<toniebox>_tap_direction` | Tap direction |
| `select.<toniebox>_age_mode` | Age mode |
| `number.<toniebox>_max_volume` | Maximum volume |
| `number.<toniebox>_lightring_brightness` | Light ring brightness |
| `button.<toniebox>_refresh` | Reload device |
| `button.<toniebox>_factory_reset` | Reset settings |

### Per Creative Tonie

| Entity | Description |
|---|---|
| `media_player.<tonie>` | Main entity with cover image and chapter overview |
| `sensor.<tonie>_chapters` | Number of chapters (incl. chapter list as attribute) |
| `sensor.<tonie>_total_duration` | Total playback duration in minutes |
| `sensor.<tonie>_remaining_time` | Remaining free capacity in minutes (max. 90 min) |
| `sensor.<tonie>_transcoding` | Transcoding status |
| `switch.<tonie>_private` | Hide Tonie from guest members |
| `switch.<tonie>_live` | Enable live mode |
| `binary_sensor.<tonie>_transcoding` | Transcoding in progress |
| `binary_sensor.<tonie>_live` | Live status |
| `binary_sensor.<tonie>_private` | Private status |
| `button.<tonie>_clear_chapters` | Remove all chapters |
| `button.<tonie>_sort_by_title` | Sort chapters alphabetically |
| `button.<tonie>_sort_by_filename` | Sort chapters by filename |
| `button.<tonie>_sort_by_date` | Sort chapters by date |
| `button.<tonie>_refresh` | Reload Tonie data |
| `select.<tonie>_sort_chapters` | Select and apply sort order |

---

## Services

### `toniebox.sort_chapters` — Sort Chapters

```yaml
service: toniebox.sort_chapters
data:
  entity_id: media_player.my_tonie
  sort_by: title   # title | filename | date
```

### `toniebox.clear_chapters` — Clear All Chapters

```yaml
service: toniebox.clear_chapters
data:
  entity_id: media_player.my_tonie
```

### `toniebox.remove_chapter` — Remove a Single Chapter

```yaml
service: toniebox.remove_chapter
data:
  entity_id: media_player.my_tonie
  chapter_id: "abc123"
```

> Chapter IDs are available as the `chapters` attribute on the media player or chapter sensor.

### `toniebox.move_chapter` — Move Chapter

```yaml
service: toniebox.move_chapter
data:
  entity_id: media_player.my_tonie
  chapter_id: "abc123"
  direction: up   # up | down
```

### `toniebox.upload_audio` — Upload Audio

```yaml
service: toniebox.upload_audio
data:
  entity_id: media_player.my_tonie
  file_path: /config/tonie_audio/story.mp3
  title: "My Story"   # optional
```

Supported formats: `mp3`, `ogg`, `wav`, `flac`, `m4a`, `aac`, `opus`.

### `toniebox.rename_tonie` — Rename Tonie

```yaml
service: toniebox.rename_tonie
data:
  entity_id: media_player.my_tonie
  name: "Bedtime Tonie"
```

### `toniebox.rename_toniebox` — Rename Toniebox

```yaml
service: toniebox.rename_toniebox
data:
  entity_id: media_player.my_toniebox
  name: "Kids Room"
```

### `toniebox.redeem_content_token` — Redeem Content Token

```yaml
service: toniebox.redeem_content_token
data:
  entity_id: media_player.my_tonie
  token: "TOKEN123"
```

### `toniebox.apply_tune` — Apply Tune to Tonie

```yaml
service: toniebox.apply_tune
data:
  entity_id: media_player.my_tonie
  tune_id: "tune-id-xyz"
```

### `toniebox.remove_tune` — Remove Tune (Restore Original)

```yaml
service: toniebox.remove_tune
data:
  entity_id: media_player.my_tonie
```

### `toniebox.redeem_voucher` — Redeem Voucher Code

```yaml
service: toniebox.redeem_voucher
data:
  code: "VOUCHER123"
```

### `toniebox.dismiss_all_notifications` — Dismiss All Notifications

```yaml
service: toniebox.dismiss_all_notifications
```

### `toniebox.accept_invitation` / `toniebox.decline_invitation` — Accept/Decline Invitation

```yaml
service: toniebox.accept_invitation
data:
  invitation_id: "invitation-id"
```

---

## Automation Examples

### Turn on light when favourite Tonie is placed

```yaml
automation:
  trigger:
    - platform: state
      entity_id: binary_sensor.benjamin_bear_currently_active
      to: "on"
  action:
    - service: light.turn_on
      target:
        entity_id: light.kids_room
```

### Volume 100% during the day, reduced to 50% at night

```yaml
automation:
  - alias: "Toniebox Volume Day"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: number.set_value
        target:
          entity_id: number.kids_room_max_volume
        data:
          value: 100

  - alias: "Toniebox Volume Night"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: number.set_value
        target:
          entity_id: number.kids_room_max_volume
        data:
          value: 50
```

### Notification when Toniebox goes offline

```yaml
automation:
  trigger:
    - platform: state
      entity_id: binary_sensor.kids_room_online
      to: "off"
      for: "00:05:00"
  action:
    - service: notify.mobile_app
      data:
        message: "Toniebox Kids Room has been offline for 5 minutes."
```

---

## Dashboard Example

```yaml
type: vertical-stack
cards:
  - type: picture-entity
    entity: media_player.my_toniebox
    show_name: true
    show_state: true
  - type: entities
    title: Creative Tonie
    entities:
      - sensor.my_tonie_chapters
      - sensor.my_tonie_total_duration
      - sensor.my_tonie_remaining_time
      - select.my_tonie_sort_chapters
  - type: horizontal-stack
    cards:
      - type: button
        entity: button.my_tonie_clear_chapters
        name: "Clear"
      - type: button
        entity: button.my_tonie_sort_by_title
        name: "A–Z"
      - type: button
        entity: button.my_tonie_refresh
        name: "Refresh"
```

---

## Debug Logging

```yaml
logger:
  default: info
  logs:
    custom_components.toniebox: debug
```

Or via **Settings → Devices & Services → Toniebox → Enable debug logging**.

> [!TIP]
> Debug logs are especially helpful when Creative Tonies or Tonieboxes are not displayed correctly — they show the exact API response fields and help diagnose parsing issues.

---

## 🤖 About Vibecoding

This integration was developed with **AI pair programming** ([Claude by Anthropic](https://anthropic.com)). Architecture, authentication flow and all platforms were built iteratively with AI assistance and tested against a real Toniebox account.

That means: it works — but **edge cases may occur**. PRs, bug reports and improvements are very welcome!

---

## Sources & Attribution

| Source | License | Usage |
|---|---|---|
| [Wilhelmsson177/tonie-api](https://github.com/Wilhelmsson177/tonie-api) | MIT | API endpoint research, Python concepts |
| [maximilianvoss/toniebox-api](https://github.com/maximilianvoss/toniebox-api) | Apache-2.0 | Concrete API URLs from `Constants.java` |
| [toniebox-reverse-engineering/teddycloud](https://github.com/toniebox-reverse-engineering/teddycloud) | GPL-3.0 | Keycloak SSO flow documentation |
| [api.tonie.cloud/v2/doc](https://api.tonie.cloud/v2/doc/) | — | Official REST API documentation |

> The endpoints used are part of the official Tonie Cloud API. No DRM protections or access controls are bypassed. The integration uses the same API as the official app.

---

## Legal

- Published under the **[MIT License](LICENSE)**
- **Not affiliated with Boxine GmbH**
- Toniebox® and Tonies® are registered trademarks of Boxine GmbH
- Use in accordance with [Boxine's Terms of Service](https://tonies.com/terms)

---

<!-- GERMAN -->
# 🇩🇪 Deutsch

## Features

- 🧸 Jede **Creative Tonie** als eigenes Gerät mit Media Player, Cover-Bild und Kapitelliste
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
└── Creative Tonie B →  ...
```

Jedes Gerät erscheint unter **Einstellungen → Geräte & Dienste → Toniebox** mit seinen eigenen Entities.

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
| `media_player.<toniebox>` | Aktuell aufgelegte Figur, Cover-Bild, Wiedergabe-Position |
| `switch.<toniebox>_kapitel_ueberspringen` | Kapitel-Überspringen per Tippen ein/aus |
| `switch.<toniebox>_vorspulen_zurueckspulen` | Scrubbing durch Kippen ein/aus |
| `switch.<toniebox>_offline_modus` | Offline-Modus |
| `switch.<toniebox>_kippen_und_klopfen` | Beschleunigungssensor ein/aus (ältere Boxen) |
| `sensor.<toniebox>_firmware` | Aktuelle Firmware-Version |
| `sensor.<toniebox>_zuletzt_gesehen` | Zeitstempel der letzten Verbindung |
| `sensor.<toniebox>_online_status` | API Online-Status (connected / offline / unknown) |
| `sensor.<toniebox>_generation` | Modell-Generation (classic / rosered / tng) |
| `sensor.<toniebox>_features` | Unterstützte Funktionen |
| `sensor.<toniebox>_zeitzone` | Konfigurierte Zeitzone |
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

### Lautstärke tagsüber 100 %, nachts auf 50 % reduzieren

```yaml
automation:
  - alias: "Toniebox Lautstärke Tag"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: number.set_value
        target:
          entity_id: number.kinderzimmer_max_lautstaerke
        data:
          value: 100

  - alias: "Toniebox Lautstärke Nacht"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: number.set_value
        target:
          entity_id: number.kinderzimmer_max_lautstaerke
        data:
          value: 50
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
> Debug-Logs sind besonders hilfreich wenn Creative Tonies oder Tonieboxen nicht korrekt angezeigt werden — sie zeigen die exakten API-Antwortfelder und helfen beim Diagnosieren von Parsing-Problemen.

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

<p align="center">Made with 🧸 + 🤖 + ☕ &nbsp;|&nbsp; <a href="https://github.com/git4sim/HA-Toniebox/issues">Report a bug / Bug melden</a></p>
