# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-12

### Added

- `hidden_in` and `refusal`: find and refuse hidden and reordering characters, named by code point, never stripped.
- `skeleton` and `reads_as`: read a text as a person would, and tell whether it reads as a header, a comment marker, a card's reply words or a protected phrase.
- `Card`: an approval card with a gutter on every body line, a rule line no body may draw, space runs shown with their count, and one-line fields that refuse line breaks, encoded words and character references.
- `Card.render(limit)`: the card cut into pieces on UTF-16 units, never splitting a surrogate pair or the frame; `is_whole` says whether it fits.
- `Entry` and `label_lines`: write notes another program reads back, where every line outside an exact entry is labelled as the model's.
- `approval-wall check` and `approval-wall render`, with `--json` on `check`, `--limit` on `render`, and exit codes 0, 1 and 2.
- The original function names (`note_refusal`, `hidden_refusal`, `marked` and the rest) for code written against the module this package grew out of.
