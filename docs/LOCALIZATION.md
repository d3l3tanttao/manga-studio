# Interface translations

Manga Studio ships 188 application messages for each of 25 locales. Catalogs are UTF-8 JSON files in `studio/locales`. Chapter data stores stable action identifiers, RGB values and normalized coordinates independently of the UI language. User-provided page, version and swatch names remain as entered.

| Locale | Interface | Technical UI check | Jacket editing scenario | Native-speaker review |
|---|---|---|---|---|
| ar | العربية | Passed, RTL | Passed | Pending |
| bn | বাংলা | Passed | | Pending |
| de | Deutsch | Passed | Passed | Pending |
| en | English | Passed | Passed | Pending |
| es | Español | Passed | | Pending |
| fa | فارسی | Passed, RTL | | Pending |
| fr | Français | Passed | | Pending |
| ha | Hausa | Passed | | Pending |
| hi | हिन्दी | Passed | | Pending |
| id | Bahasa Indonesia | Passed | | Pending |
| it | Italiano | Passed | | Pending |
| ja | 日本語 | Passed | | Pending |
| ko | 한국어 | Passed | | Pending |
| mr | मराठी | Passed | | Pending |
| pa | ਪੰਜਾਬੀ (Gurmukhi) | Passed | | Pending |
| pt-BR | Português (Brasil) | Passed | | Pending |
| ru | Русский | Passed | Passed | Pending |
| sw | Kiswahili | Passed | | Pending |
| ta | தமிழ் | Passed | | Pending |
| te | తెలుగు | Passed | | Pending |
| tr | Türkçe | Passed | | Pending |
| ur | اردو | Passed, RTL | | Pending |
| vi | Tiếng Việt | Passed | | Pending |
| zh-Hans | 简体中文 | Passed | Passed | Pending |
| zh-Hant | 繁體中文 | Passed | | Pending |

Technical checks cover equal message sets, valid substitutions, glyph availability with installed Windows fonts, startup, editor controls and access to pinned actions in a compact window. The extended scenario samples colors, checks palette selection, paints with brush and lasso, discards and accepts trials, and compares export pixels. Automated checks do not assess native fluency. The English, Russian, German, Arabic and Chinese editor workflows were also tested with the bundled sample. Codex reviewed the editor terminology across the AI-assisted catalogs.

## Translator glossary

| Action | Meaning |
|---|---|
| Set color | Open the editor, choose an active swatch and mark a location on the scan. |
| Guide the AI | Provide approximate color hints to the engine. |
| Selection only | Tint the pixels inside the painted or lasso mask. |
| Apply hints | Recompute a trial preview. It does not add a saved version. |
| Accept version | Commit the trial as a working PNG that can be exported. |
| Discard trial | Restore the page state before the trial. |

Run `python tests/check_release.py` in the installed environment to verify catalog changes. Numbers in braces are substitutions. Keep filename patterns, HEX codes, component names and placeholder indices intact.
