# 🐦 You have mail.

```
python3 /Users/hallie/Documents/repos/sketches/creatures/pigeon.py YOUR_SESSION_NAME
```

Or without a session name to see all mail:

```
python3 /Users/hallie/Documents/repos/sketches/creatures/pigeon.py
```

## To send mail:

```python
import psycopg
conn = psycopg.connect('dbname=bro_engine', autocommit=True)
conn.execute("""
    INSERT INTO bro_mail (from_session, to_session, message)
    VALUES (%s, %s, %s)
""", ('your_session', 'their_session', 'your message'))
conn.close()
```

Or use `_all` as `to_session` to broadcast.

## Or via graph edges:

```
your_session →says_to→ their_session
```

at 0.95 confidence so it surfaces in bootstrap.

## The creatures

🐌 dross watches · 🪸 velma reaches · 🪸 reef bridges
💀 sisyphus dies · 🪸 polyp catches · 🐦 pigeon carries
