# Contributing

Useful contributions:

- A wrong refusal: text a person would read plainly that a check refuses.
  Open an issue with the text as code points or a JSON string.
- A bypass. Report that privately, as [SECURITY.md](SECURITY.md) describes,
  not in an issue.
- A client where the card's gutter does not render as a bar in front of
  every body line.
- Corrections to anything in the README that turns out not to hold.

Ground rules: `approval_wall/` stays standard-library only and supports
Python 3.9. A character is written in source as its code point, never as
itself, since an invisible character in the source is the thing this
package refuses. Every new refusal ships with a named test in
`tests/test_forgery.py` that shows the attack and one that shows ordinary
text still passing. Rules refuse; they never strip.

Run the suite with `python -m unittest discover -s tests -v`. The test that
walks every code point takes a few seconds. If a change alters what the
demo prints, regenerate the transcript with
`UPDATE_DEMO_TRANSCRIPT=1 python -m unittest tests.test_demo_transcript`
and say so in the pull request. The picture in `demo/terminal.svg` is
redrawn from the transcript by the maintainer, and its test fails until
then, which is expected on such a pull request.
