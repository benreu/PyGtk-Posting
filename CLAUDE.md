# PyGtk-Posting

- Do each change on a new branch off `develop`. Do not commit or push until
  asked; a request to commit covers only the work done up to then.
- Database changes ship as a new block in `src/db/update_db_minor.sql` plus a
  `VERSION_MINOR` bump in `src/db/version.py`; the app applies them at startup.
  Never apply SQL to a database by hand.
- Every window has a help page in `help/C/pygtk-posting`, the one its
  `user_manual.bind_f1` call names. When a change alters what a window does,
  update that page; a new window needs a page and a `bind_f1` line. Run
  `python3 -m unittest discover -s tests/help` before finishing.
- Bugs not yet fixed are listed in the memory note
  `posting-bugs-found-writing-help`, and their help pages describe them as
  limitations. When you fix one, update its page and remove its line from the
  note.
