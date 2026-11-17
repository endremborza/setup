"""Attach to a session `moac tmux` opened: switch to it inside tmux, attach from outside."""

import os

from .tmux import PREFIX, Session, sessions


def main(session: Session = "") -> None:
    """Attach to a live `moac tmux` session; TAB completes their names.

    SESSION is the name without `PREFIX`. Without it the only live session is taken, and
    several are listed instead.
    """
    live = sessions()
    if not session:
        if not live:
            raise SystemExit("no moac tmux session is running")
        if len(live) > 1:
            raise SystemExit("several moac tmux sessions; name one: " + " ".join(live))
        session = live[0]
    session = session.removeprefix(PREFIX)
    if session not in live:
        raise SystemExit(
            f"no moac tmux session '{session}' (live: {' '.join(live) or 'none'})"
        )
    verb = "switch-client" if os.environ.get("TMUX") else "attach-session"
    os.execvp("tmux", ["tmux", verb, "-t", f"={PREFIX}{session}"])
