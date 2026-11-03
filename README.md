# Web Board (Forum)

**Category:** Web

## Problem

Create a forum for you and your buddies to post, administer and share thoughts and ideas.

## Solution

SQLite tables for topics and replies behind a stdlib HTTP server. The index lists threads with reply counts, `/topic/<id>` renders the thread and a reply form, and `POST /new` / `POST /topic/<id>/reply` insert records and redirect. All user text is HTML-escaped.

## How to run

Requires Python 3.8+ and no third-party packages.

```bash
python3 main.py --port 8002 --db forum.db
python3 main.py --demo
```

## Example

```text
topic title present: True
reply present: True
listing shows 1 reply: True
```

## Attribution

The problem statement is from [karan/Projects](https://github.com/karan/Projects), a list of practical projects that anyone can solve in any programming language (MIT License, Copyright (c) 2013 Karan Goel). The Python solution in this repository was implemented by [bspreston-esq](https://github.com/bspreston-esq).

This repository is part of the [Projects-Python-All](https://github.com/bspreston-esq/Projects-Python-All) collection.
