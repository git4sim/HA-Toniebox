# 🧸 Toniebox Integration for Home Assistant

A custom Home Assistant integration that merges the **[tonie-api](https://tonie-api.readthedocs.io)** Python cloud library with the feature concepts from **[maximilianvoss/toniebox-api](https://github.com/maximilianvoss/toniebox-api)** into a single, HACS-compatible HA integration.

> **Disclaimer:** This project is not affiliated with Boxine GmbH (tonies.de). Use at your own risk. The underlying API may change at any time.

---

## ✨ Features

| Feature | Platform |
|---|---|
| Creative Tonie as media player entity | `media_player` |
| Chapter count per tonie | `sensor` |
| Total audio duration per tonie | `sensor` |
| Number of creative tonies per household | `sensor` |
| Clear all chapters (button) | `button` |
| Sort chapters by title / filename / date | `button` + `select` |
| Refresh data | `button` |
| Upload audio file as chapter | `service` |
| Sort chapters via service call | `service` |
| Config Flow UI setup (no YAML needed) | `config_flow` |
| HACS compatible | — |

---

## 📦 Installation

### Via HACS (recommended)

1. In Home Assistant, open **HACS → Integrations**.
2. Click the **⋮ menu** → **Custom repositories**.
3. Add this repository URL and select category **Integration**.
4. Search for **Toniebox** and click **Download**.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/toniebox/` folder into your HA `config/custom_components/` directory.
2. Restart Home Assistant.

---

## ⚙️ Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Toniebox**.
3. Enter your **Toniebox account email** and **password** (same as the Toniebox app).
4. Done — all households and creative tonies are automatically discovered.

---

## 🏠 Entities Created

For each **household**:
- `sensor.toniebox_<household>_creative_tonies` — number of creative tonies

For each **creative tonie**:
- `media_player.toniebox_<name>` — main entity with cover art, chapter list, attributes
- `sensor.toniebox_<name>_chapter_count` — number of chapters loaded
- `sensor.toniebox_<name>_total_duration` — total playback duration in minutes
- `button.toniebox_<name>_clear_all_chapters`
- `button.toniebox_<name>_sort_chapters_by_title`
- `button.toniebox_<name>_sort_chapters_by_filename`
- `button.toniebox_<name>_sort_chapters_by_date`
- `button.toniebox_<name>_refresh`
- `select.toniebox_<name>_sort_chapters` — sort & apply in one step

---

## 🔧 Services

### `toniebox.upload_audio`

Upload a local MP3/audio file as a new chapter to a creative tonie.

```yaml
service: toniebox.upload_audio
data:
  entity_id: media_player.toniebox_mein_tonie
  file_path: /config/tonie_audio/story.mp3
  title: "Bedtime Story"
```

> The file must be accessible from the Home Assistant host filesystem.

### `toniebox.clear_chapters`

Remove all chapters from a creative tonie.

```yaml
service: toniebox.clear_chapters
data:
  entity_id: media_player.toniebox_mein_tonie
```

### `toniebox.sort_chapters`

Sort chapters on a creative tonie.

```yaml
service: toniebox.sort_chapters
data:
  entity_id: media_player.toniebox_mein_tonie
  sort_by: title   # title | filename | date
```

---

## 🤖 Automation Examples

### Auto-sort chapters when new content is added

```yaml
automation:
  alias: "Sort Tonie chapters after upload"
  trigger:
    - platform: state
      entity_id: sensor.toniebox_mein_tonie_chapter_count
  action:
    - service: toniebox.sort_chapters
      data:
        entity_id: media_player.toniebox_mein_tonie
        sort_by: title
```

### Dashboard card for a creative tonie

```yaml
type: vertical-stack
cards:
  - type: picture-entity
    entity: media_player.toniebox_mein_tonie
    show_name: true
    show_state: true
  - type: entities
    entities:
      - sensor.toniebox_mein_tonie_chapter_count
      - sensor.toniebox_mein_tonie_total_duration
      - select.toniebox_mein_tonie_sort_chapters
  - type: horizontal-stack
    cards:
      - type: button
        entity: button.toniebox_mein_tonie_clear_all_chapters
        name: "🗑 Clear"
      - type: button
        entity: button.toniebox_mein_tonie_sort_chapters_by_title
        name: "🔤 Sort A-Z"
      - type: button
        entity: button.toniebox_mein_tonie_refresh
        name: "🔄 Refresh"
```

---

## 🔄 Data Update

The integration polls the Toniebox cloud every **5 minutes** by default.  
Force a refresh anytime using the `button.<tonie>_refresh` entity or via:

```yaml
service: homeassistant.update_entity
data:
  entity_id: media_player.toniebox_mein_tonie
```

---

## 📚 API Sources

This integration unifies:

- **[tonie-api (Python)](https://github.com/Wilhelmsson177/tonie-api)** — REST cloud API wrapper (`pip install tonie-api`)
- **[toniebox-api (Java)](https://github.com/maximilianvoss/toniebox-api)** — Feature concepts: chapter management, sorting, upload, household model
- **[api.tonie.cloud/v2](https://api.tonie.cloud/v2/doc/)** — Official undocumented Boxine REST API

---

## 🛠 Requirements

- Home Assistant ≥ 2023.1
- Python ≥ 3.11
- `tonie-api==0.1.2` (installed automatically)
- Active Toniebox account (free)

---

## 📄 License

MIT License — see [LICENSE](LICENSE)
