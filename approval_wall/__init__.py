"""approval-wall: keep an approval card from being forged by the text inside it.

Three parts, each usable alone:

- the text rule (text.py): hidden and reordering characters are found and
  refused, never stripped, and a text is read the way a person reads it
  (its skeleton) before it is compared with any protected phrase;
- the card (card.py): a frame no body can imitate, cut to a transport limit
  without ever cutting the frame;
- the entry grammar (entry.py): notes one program writes and another reads
  back, where every line outside an exact entry is labelled as the model's.

The names hidden, hidden_in, skeleton, marked, note_refusal, hidden_refusal,
starts_header, has_marker, names, CONFUSABLES and NOTICE_WORDS are kept from
the module this package grew out of, so code written against it imports this
package unchanged.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .text import (CONFUSABLES, NOTICE_WORDS, REPLY_WORDS, has_marker, hidden, hidden_in,  # noqa: E402
                   hidden_refusal, marked, names, note_refusal, reads_as, refusal, skeleton, starts_header)

__all__ = [
    "CONFUSABLES", "NOTICE_WORDS", "REPLY_WORDS", "has_marker", "hidden", "hidden_in", "hidden_refusal",
    "marked", "names", "note_refusal", "reads_as", "refusal", "skeleton", "starts_header",
]
