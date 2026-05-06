"""
client_manager.py
-----------------
Loads client config files from the clients/ folder.
Each client is a .json file. Set "active": false to skip a client.

Main functions:
  load_all_clients()     → returns a list of all active client dicts
  load_client(client_id) → returns one specific client dict
"""

import os
import json


CLIENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "clients")


def load_all_clients() -> list:
    """
    Read every .json file in the clients/ folder.
    Returns a list of client dicts — only those marked "active": true.
    """
    clients = []
    clients_path = os.path.abspath(CLIENTS_DIR)

    if not os.path.exists(clients_path):
        print(f"  Warning: clients/ folder not found at {clients_path}")
        return []

    for filename in sorted(os.listdir(clients_path)):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(clients_path, filename)
        try:
            with open(filepath, "r") as f:
                client = json.load(f)

            # Skip inactive clients
            if not client.get("active", True):
                print(f"  Skipping {filename} (inactive)")
                continue

            # Make sure required fields exist
            _validate(client, filename)

            clients.append(client)

        except json.JSONDecodeError as e:
            print(f"  Error reading {filename}: {e}  — skipping")
        except ValueError as e:
            print(f"  Config error in {filename}: {e}  — skipping")

    return clients


def load_client(client_id: str) -> dict:
    """
    Load one specific client by their client_id.
    Raises ValueError if not found.
    """
    all_clients = load_all_clients()
    for client in all_clients:
        if client.get("client_id") == client_id:
            return client
    raise ValueError(f"Client '{client_id}' not found in clients/ folder.")


def _validate(client: dict, filename: str):
    """Check that a client config has all required fields."""
    required = ["client_id", "business_name", "email"]
    for field in required:
        if not client.get(field):
            raise ValueError(
                f"Missing required field '{field}' in {filename}"
            )
