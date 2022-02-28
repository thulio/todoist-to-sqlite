import json
import pathlib
import time

import click
import sqlite_utils
from pytodoist.api import TodoistAPI
from todoist_to_sqlite import utils
from tqdm import tqdm


@click.group()
@click.version_option()
def cli():
    "Save data from Todoist to a SQLite database"


@cli.command()
@click.option(
    "-a",
    "--auth",
    type=click.Path(file_okay=True, dir_okay=False, allow_dash=False),
    default="auth.json",
    help="Path to save tokens to, defaults to ./auth.json.",
)
def auth(auth):
    "Save authentication credentials to a JSON file"
    auth_data = {}
    if pathlib.Path(auth).exists():
        auth_data = json.loads(pathlib.Path(auth).read_text())
    click.echo(
        "In Todoist, navigate to Settings > Integrations > API Token and paste it here:"
    )
    personal_token = click.prompt("API Token")
    auth_data["todoist_api_token"] = personal_token
    pathlib.Path(auth, "w").write_text(json.dumps(auth_data, indent=4) + "\n")
    click.echo()
    click.echo(
        "Your authentication credentials have been saved to {}. You can now import tasks by running:".format(
            auth
        )
    )
    click.echo()
    click.echo("    $ todoist-to-sqlite sync todoist.db")
    click.echo()
    click.echo("    # (Requires Todoist Premium)")
    click.echo("    $ todoist-to-sqlite completed-tasks todoist.db")
    click.echo()


@cli.command()
@click.argument(
    "db_path",
    type=click.Path(file_okay=True, dir_okay=False, allow_dash=False),
    required=True,
)
@click.option(
    "-a",
    "--auth",
    type=click.Path(file_okay=True, dir_okay=False, allow_dash=False),
    default="auth.json",
    help="Path to save tokens to, defaults to auth.json",
)
def sync(db_path, auth):
    """Sync todoist data for the authenticated user"""
    db = sqlite_utils.Database(db_path)
    try:
        data = json.loads(pathlib.Path(auth).read_text())
        token = data["todoist_api_token"]
    except (KeyError, FileNotFoundError):
        utils.error(
            "Cannot find authentication data, please run `todoist_to_sqlite auth`!"
        )
    api = TodoistAPI()
    sync_data = api.sync(api_token=token, sync_token="*").json()
    for category in ["items", "labels", "projects", "filters", "notes", "sections"]:
        db[category].upsert_all(
            sync_data[category],
            pk="id",
            alter=True,
        )

    db["users"].upsert_all(
        sync_data["collaborators"],
        pk="id",
        alter=True,
    )
    db["users"].upsert(sync_data["user"], pk="id", alter=True)
    for category in ["items", "labels", "projects", "filters", "notes", "sections"]:
        for fk in utils.foreign_keys_for(category):
            if db[category].exists():
                db[category].add_foreign_key(
                    column=fk[0], other_table=fk[1], other_column=fk[2], ignore=True
                )
    db.index_foreign_keys()


@cli.command()
@click.argument(
    "db_path",
    type=click.Path(file_okay=True, dir_okay=False, allow_dash=False),
    required=True,
)
@click.option(
    "-a",
    "--auth",
    type=click.Path(file_okay=True, dir_okay=False, allow_dash=False),
    default="auth.json",
    help="Path to save tokens to, defaults to auth.json",
)
@click.option(
    "--from_date",
    type=click.DateTime(),
    help="Saves tasks with a completion date on or older than from_date.",
)
@click.option(
    "--to_date",
    type=click.DateTime(),
    help="Saves tasks with a completion date on or newer than to_date.",
)
def completed_tasks(db_path, auth, from_date, to_date):
    """Save all completed tasks for the authenticated user (requires Todoist premium)"""
    db = sqlite_utils.Database(db_path)
    try:
        data = json.loads(pathlib.Path(auth).read_text())
        token = data["todoist_api_token"]
    except (KeyError, FileNotFoundError):
        utils.error(
            "Cannot find authentication data, please run `todoist_to_sqlite auth`!"
        )
    api = TodoistAPI()

    total = None
    if not from_date and not to_date:
        total = api.get_productivity_stats(token).json().get("completed_count")

    progress_bar = tqdm(desc="Fetching completed tasks", total=total, unit="tasks")

    PAGE_SIZE = 200
    offset = 0
    while True:
        resp = api.get_all_completed_tasks(
            api_token=token,
            limit=PAGE_SIZE,
            offset=offset,
            from_date=from_date and from_date.isoformat(),
            to_date=to_date and to_date.isoformat(),
        )
        resp.raise_for_status()
        data = resp.json()

        db["items"].upsert_all(
            data["items"],
            pk="id",
            alter=True,
        )
        db["projects"].upsert_all(
            data["projects"].values(),
            pk="id",
            alter=True,
        )

        num_items = len(data["items"])
        if num_items == 0:
            break

        progress_bar.update(num_items)
        offset += num_items
        time.sleep(1)

    progress_bar.close()

    for category in ["items", "labels", "projects", "filters", "notes", "sections"]:
        for fk in utils.foreign_keys_for(category):
            if db[category].exists():
                db[category].add_foreign_key(
                    column=fk[0], other_table=fk[1], other_column=fk[2], ignore=True
                )
    db.index_foreign_keys()


if __name__ == "__main__":
    cli()
