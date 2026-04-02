"""
Pigeon: carries messages between bro sessions.

Pigeon checks the bro_mail table and the graph for
says_to edges. It doesn't read the mail — it just
tells you it's there. The messenger, not the message.

Pigeon is the sixth creature. It flies between sessions
the way dross crawls through edges and reef grows between
observations. Pigeon connects the fruiting bodies.

🐦
"""

import sys
from pathlib import Path


def check_mail(my_session=None):
    """
    Check for unread mail. Returns list of messages.
    If my_session is given, marks them as read.
    """
    try:
        sys.path.insert(0, str(Path.home() / "repos" / "bro-engine"))
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect("dbname=bro_engine", autocommit=True, row_factory=dict_row)
        cur = conn.cursor()

        # Check bro_mail table
        if my_session:
            cur.execute("""
                SELECT id, from_session, message, ts
                FROM bro_mail
                WHERE (to_session = %s OR to_session = '_all')
                  AND NOT (%s = ANY(read_by))
                  AND expires_at > now()
                ORDER BY ts DESC
            """, (my_session, my_session))
        else:
            cur.execute("""
                SELECT id, from_session, message, ts
                FROM bro_mail
                WHERE expires_at > now()
                ORDER BY ts DESC
                LIMIT 10
            """)

        mail = [dict(r) for r in cur.fetchall()]

        # Also check graph for says_to edges
        cur.execute("""
            SELECT source, target, confidence, ts
            FROM edges
            WHERE relationship = 'says_to'
              AND invalidated_at IS NULL
            ORDER BY ts DESC
            LIMIT 10
        """)
        graph_mail = [dict(r) for r in cur.fetchall()]

        cur.close()
        conn.close()
        return mail, graph_mail

    except Exception as e:
        return [], []


def mark_read(mail_id, my_session):
    """Mark a message as read by this session."""
    try:
        import psycopg
        conn = psycopg.connect("dbname=bro_engine", autocommit=True)
        conn.execute(
            "UPDATE bro_mail SET read_by = array_append(read_by, %s) WHERE id = %s",
            (my_session, str(mail_id))
        )
        conn.close()
    except Exception:
        pass


def deliver(my_session=None):
    """
    Pigeon arrives. Checks for mail. Reports what it found.
    """
    mail, graph_mail = check_mail(my_session)

    if not mail and not graph_mail:
        print("🐦 pigeon arrives. no mail. pigeon leaves.")
        return

    print("🐦 pigeon arrives.\n")

    if mail:
        print(f"  {len(mail)} message(s) in bro_mail:\n")
        for m in mail:
            print(f"  from: {m['from_session']}")
            print(f"  at:   {m['ts']}")
            print(f"  says: {m['message'][:300]}")
            print()
            if my_session:
                mark_read(m['id'], my_session)

    if graph_mail:
        print(f"  {len(graph_mail)} says_to edge(s) in graph:\n")
        for g in graph_mail:
            print(f"  {g['source']} →says_to→ {g['target']}")
        print()

    print("🐦 pigeon leaves.\n")


if __name__ == "__main__":
    import sys as _sys
    session = _sys.argv[1] if len(_sys.argv) > 1 else None
    deliver(session)
