<p align="center">
  <img src="logo.png" alt="HA-Toniebox Logo" width="180" />
</p>

<h1 align="center">HA-Toniebox</h1>

<p align="center">
  <strong>Unofficial Home Assistant integration for the Toniebox / Tonie Cloud</strong><br/>
  Manage your Creative Tonies, browse chapters, sort & clear content — all from Home Assistant.
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-orange.svg?logo=home-assistant&logoColor=white" alt="HACS Custom"/></a>
  <img src="https://img.shields.io/badge/version-1.1.0-blue" alt="Version"/>
  <img src="https://img.shields.io/badge/HA-2023.1%2B-brightgreen?logo=home-assistant" alt="Home Assistant"/>
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="MIT License"/>
  <img src="https://img.shields.io/badge/vibecoded-%F0%9F%A4%96%20100%25-blueviolet" alt="Vibecoded"/>
</p>

---

> ⚠️ **Disclaimer — Please read before using**
>
> This project is **not affiliated with, endorsed by, or connected to Boxine GmbH** (the makers of Toniebox / tonies.de) **in any way**.
> It uses the undocumented Tonie Cloud REST API which **may change or break at any time without notice**.
> Use entirely **at your own risk**. No warranty, no guarantee, no support from Boxine.
>
> This integration was **vibecoded** — generated with AI assistance (Claude by Anthropic) and lightly reviewed. It is a community experiment, not production software. Treat it accordingly.

---

## ✨ Features

| What | How |
|---|---|
| Creative Tonie as HA media player | `media_player.*` entity with cover art & chapter list |
| Chapter count & total duration | `sensor.*` entities, always up to date |
| Household overview | Number of Creative Tonies per household |
| Sort chapters (title / filename / date) | One-tap `button.*` or `select.*` entity |
| Clear all chapters | `button.*` entity + service call |
| Refresh on demand | `button.*` + auto-poll every 5 min |
| Full service API | `toniebox.sort_chapters`, `toniebox.clear_chapters`, `toniebox.upload_audio` |
| Config Flow — no YAML needed | Set up via Settings → Integrations |
| HACS compatible | Add as custom repository |

---

## 📦 Installation via HACS (recommended)

1. Make sure [HACS](https://hacs.xyz) is installed in your Home Assistant.
2. In Home Assistant, go to **HACS → Integrations**.
3. Click the **⋮ menu** (top right) → **Custom repositories**.
4. Add the following URL and select category **Integration**:
   ```
   https://github.com/YOUR_USERNAME/HA-Toniebox
   ```
5. Search for **Toniebox** in HACS and click **Download**.
6. Restart Home Assistant.
7. Go to **Settings → Devices & Services → Add Integration** → search **Toniebox**.
8. Enter your Toniebox account email and password → Done.

---

## 🔧 Manual Installation

1. Download the latest release ZIP or clone this repo.
2. Copy the folder `custom_components/toniebox/` into your HA config directory:
   ```
   /config/custom_components/toniebox/
   ```
3. Restart Home Assistant.
4. Set up via **Settings → Devices & Services → Add Integration → Toniebox**.

---

## ⚙️ Configuration

No YAML required. Enter your **Toniebox account credentials** (same email/password as the Toniebox app or my.tonies.com) in the UI config flow.

---

## 🏠 Entities

For each **household**:
- `sensor.<household>_creative_tonies` — number of Creative Tonies

For each **Creative Tonie**:
- `media_player.toniebox_<name>` — main entity: cover art, chapter list, attributes
- `sensor.<name>_chapter_count` — number of chapters
- `sensor.<name>_total_duration` — total audio length in minutes
- `button.<name>_clear_all_chapters` — removes all chapters
- `button.<name>_sort_by_title` / `_sort_by_filename` / `_sort_by_date`
- `button.<name>_refresh`
- `select.<name>_sort_chapters` — sort & apply in one step

---

## 🔧 Services

### `toniebox.sort_chapters`
```yaml
service: toniebox.sort_chapters
data:
  entity_id: media_player.toniebox_mein_tonie
  sort_by: title   # title | filename | date
```

### `toniebox.clear_chapters`
```yaml
service: toniebox.clear_chapters
data:
  entity_id: media_player.toniebox_mein_tonie
```

### `toniebox.upload_audio`
```yaml
service: toniebox.upload_audio
data:
  entity_id: media_player.toniebox_mein_tonie
  file_path: /config/tonie_audio/maerchen.mp3
  title: "Rotkäppchen"
```

---

## 🎛 Dashboard Example

```yaml
type: vertical-stack
cards:
  - type: picture-entity
    entity: media_player.toniebox_mein_tonie
    show_name: true
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
        entity: button.toniebox_mein_tonie_sort_by_title
        name: "🔤 A–Z"
      - type: button
        entity: button.toniebox_mein_tonie_refresh
        name: "🔄 Refresh"
```

---

## 🤖 Vibecoded — What does that mean?

This integration was built with **AI pair-programming** (Claude by Anthropic) rather than written fully by hand. The code was generated, reviewed, debugged iteratively with AI help, and refined based on actual error output.

This means:
- It works (tested against a real Toniebox account), but **edge cases may exist**
- Code quality is solid but not battle-hardened production software
- PRs and improvements are very welcome!

---

## 📚 Sources & Attribution

This project stands on the shoulders of others' reverse-engineering work. All sources are credited here to ensure transparency and avoid any misunderstandings:

| Source | What was used |
|---|---|
| **[Wilhelmsson177/tonie-api](https://github.com/Wilhelmsson177/tonie-api)** (MIT) | API endpoint discovery, Python library concept, `tonie-api` PyPI package |
| **[maximilianvoss/toniebox-api](https://github.com/maximilianvoss/toniebox-api)** (Apache-2.0) | All concrete API endpoint URLs (`Constants.java`): login, households, creative tonies, file upload |
| **[toniebox-reverse-engineering/teddycloud](https://github.com/toniebox-reverse-engineering/teddycloud)** | Keycloak SSO login flow documentation and community research |
| **[croesnick/toniebox-audio-match #15](https://github.com/croesnick/toniebox-audio-match/issues/15)** | SSO / OpenID Connect endpoint documentation |
| **Home Assistant Developer Docs** | Integration architecture, config flow, coordinator pattern |

### API Endpoints used (source: maximilianvoss/toniebox-api)

```
POST https://login.tonies.com/auth/realms/tonies/protocol/openid-connect/token
GET  https://api.tonie.cloud/v2/me
GET  https://api.tonie.cloud/v2/households
GET  https://api.tonie.cloud/v2/households/{id}/creativetonies
GET  https://api.tonie.cloud/v2/households/{id}/creativetonies/{id}
PATCH https://api.tonie.cloud/v2/households/{id}/creativetonies/{id}
```

These are **undocumented, unofficial endpoints** belonging to Boxine GmbH. This project does not scrape, abuse, or bypass any security mechanisms. It uses the same endpoints that the official Toniebox mobile app uses.

---

## ⚖️ Legal

- This project is released under the **MIT License** — see [LICENSE](LICENSE)
- **Not affiliated with Boxine GmbH** in any way
- Toniebox®, Tonies® are registered trademarks of Boxine GmbH
- The Tonie Cloud API is undocumented and unofficial — no guarantee of continued functionality
- This project does not circumvent any DRM, copy protection, or access controls
- Use in compliance with Boxine's [Terms of Service](https://tonies.com/terms)

---

## 🤝 Contributing

PRs, bug reports, and feature requests are welcome!  
Open an issue or submit a pull request.

---

<p align="center">Made with 🧸 + 🤖 + ☕</p>
