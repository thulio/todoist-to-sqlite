import time
import click
import pathlib
import json
import sqlite_utils
from tqdm import tqdm
from todoist_to_sqlite import utils
from pytodoist import todoist
from pytodoist.api import TodoistAPI


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
        auth_data = json.load(open(auth))
    click.echo(
        "In Todoist, navigate to Settings > Integrations > API Token and paste it here:"
    )
    personal_token = click.prompt("API Token")
    auth_data["todoist_api_token"] = personal_token
    open(auth, "w").write(json.dumps(auth_data, indent=4) + "\n")
    click.echo()
    click.echo(
        "Your authentication credentials have been saved to {}. You can now import tasks by running".format(
            auth
        )
    )
    click.echo()
    click.echo("    todoist-to-sqlite tasks todoist.db")
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
        data = json.load(open(auth))
        token = data["todoist_api_token"]
    except (KeyError, FileNotFoundError):
        utils.error(
            "Cannot find authentication data, please run `todoist_to_sqlite auth`!"
        )
    api = TodoistAPI()
    sync_data = api.sync(api_token=token, sync_token="*").json()
    for category in ['items', 'labels', 'projects', 'filters', 'notes', 'sections']:
        db[category].upsert_all(sync_data[category], pk="id", alter=True)

    db['users'].upsert_all(sync_data['collaborators'], pk="id")
    db['users'].upsert(sync_data['user'], pk='id')

    utils.add_foreign_keys(db)


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
def completed_tasks(db_path, auth):
    """Save tasks for the authenticated user"""
    db = sqlite_utils.Database(db_path)
    try:
        data = json.load(open(auth))
        token = data["todoist_api_token"]
    except (KeyError, FileNotFoundError):
        utils.error(
            "Cannot find authentication data, please run `todoist_to_sqlite auth`!"
        )
    api = TodoistAPI()
    stats = api.get_productivity_stats(token)
    PAGE_SIZE = 50
    offset = 0

    progress_bar = tqdm(
        desc="Fetching completed tasks",
        total=stats.json().get('completed_count')
    )

    while True:
        data = api.get_all_completed_tasks(
            api_token=token, limit=PAGE_SIZE, offset=offset).json()
        db['items'].upsert_all(data['items'], pk='id', alter=True)
        db['projects'].upsert_all(
            data['projects'].values(), pk='id', alter=True)
        num_items = len(data['items'])
        if num_items == 0 or True:
            break
        progress_bar.update(num_items)
        offset += num_items
        time.sleep(1)
    utils.add_foreign_keys(db, tables=["users", "projects"])


if __name__ == "__main__":
    cli()
