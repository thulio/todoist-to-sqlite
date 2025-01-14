import sys

import click

FOREIGN_KEYS = [
    ("items", "parent_id", "items", "id"),
    ("items", "project_id", "projects", "id"),
    ("items", "user_id", "users", "id"),
    ("items", "added_by_uid", "users", "id"),
    ("items", "assigned_by_uid", "users", "id"),
    ("items", "section_id", "sections", "id"),
    ("notes", "item_id", "items", "id"),
    ("notes", "project_id", "projects", "id"),
    ("projects", "parent_id", "projects", "id"),
    ("users", "inbox_project", "projects", "id"),
]


def error(message):
    click.secho(message, bold=True, fg="red")
    sys.exit(-1)


def foreign_keys_for(table):
    for (t, *fk) in FOREIGN_KEYS:
        if t == table:
            yield fk
