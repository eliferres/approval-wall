# Security

A bypass is any text that gets past these rules and reads, to a person, as part of a card's frame, its release line, an exact entry, or a protected phrase: a hidden character `hidden_in` misses, a body that draws a line the frame did not, a one-line field that ends its line, a cut that breaks the frame, or a notes file that `label_lines` labels as the bot's when the bot did not write it.

## Reporting one

Report it privately through GitHub's private vulnerability reporting: the "Report a vulnerability" button on this repository's Security tab. Please do not open a public issue for a bypass. Include the exact input (as code points or a JSON string, so nothing invisible is lost in transit), the Python version, and the client where it rendered.

You will get a reply within two business days. A confirmed bypass earns a named test in `tests/test_forgery.py` and a release that refuses it, and the report is credited in the changelog unless you ask otherwise.

## The trust assumption

Model text must reach the notes file only through `Entry.text`. Anything that writes the file directly can forge a complete entry with its own key, and the grammar cannot tell it from a real one. A forged entry written that way is outside what this package can catch.

## In scope

- `hidden`, `hidden_in`, `refusal`, `skeleton` and `reads_as` missing a character or a shape they claim to catch.
- `Card` rendering a body or a field that imitates the frame, or pieces that exceed the limit or cut the frame.
- `Entry` and `label_lines` labelling a line as part of an entry when it is not.

## Out of scope

- A look-alike letter outside the table that makes `reads_as` miss a phrase. The table is short by design and the README says so; the frame and the entry grammar are the defence. A look-alike that also defeats the frame or the grammar is in scope.
- What this package is not: an approval system (ids, expiry, delivery and acting on a reply are the caller's) or a sandbox for a model.
