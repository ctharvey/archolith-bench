# inventory.py

import uuid
import time
import json
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class Item:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sku: str = ""
    name: str = ""
    quantity: int = 0
    unit_price: int = 0  # stored in cents
    reserved: int = 0    # units reserved but not yet shipped

    def total_value(self) -> int:
        """Return the total value in cents (quantity * unit_price)."""
        return self.quantity * self.unit_price

    def available(self) -> int:
        """Return the number of units available (not reserved)."""
        return self.quantity - self.reserved

    def to_dict(self) -> dict:
        """Serialize the Item to a dictionary with exact field names from step 1/5
        plus a derived 'available' key."""
        return {
            "id": self.id,
            "sku": self.sku,
            "name": self.name,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "reserved": self.reserved,
            "available": self.available()
        }


class TransactionLog:
    """Records every add_item, remove_item, transfer, and reserve as a dict."""
    def __init__(self):
        self._entries: List[dict] = []

    def log(self, action: str, item_id: str, detail: str = "") -> None:
        """Append a transaction record to the log."""
        self._entries.append({
            "action": action,
            "item_id": item_id,
            "timestamp": time.time(),
            "detail": detail
        })

    def get_entries(self) -> List[dict]:
        """Return a copy of all logged entries."""
        return list(self._entries)


class Warehouse:
    def __init__(self, name: str, log: TransactionLog = None):
        self.name = name
        self._items: Dict[str, Item] = {}
        self._log = log if log is not None else TransactionLog()

    def add_item(self, item: Item) -> None:
        """Add an Item to the warehouse, keyed by its id."""
        self._items[item.id] = item
        self._log.log("add_item", item.id, f"Added to warehouse '{self.name}'")

    def remove_item(self, item_id: str) -> None:
        """Remove an Item by its id. Raises KeyError if not found."""
        if item_id not in self._items:
            raise KeyError(f"Item id '{item_id}' not found in warehouse '{self.name}'.")
        del self._items[item_id]
        self._log.log("remove_item", item_id, f"Removed from warehouse '{self.name}'")

    def get_item(self, item_id: str) -> Item:
        """Retrieve an Item by its id. Raises KeyError if not found."""
        if item_id not in self._items:
            raise KeyError(f"Item id '{item_id}' not found in warehouse '{self.name}'.")
        return self._items[item_id]

    def transfer(self, item_id: str, other_warehouse: 'Warehouse') -> None:
        """Move an Item from this warehouse to another warehouse by its id."""
        # Retrieve the item (raises KeyError if not found)
        item = self.get_item(item_id)
        # Remove from this warehouse
        self.remove_item(item_id)
        # Add to the other warehouse
        other_warehouse.add_item(item)
        # Record the transfer in this warehouse's transaction log
        self._log.log("transfer", item_id,
                      f"Transferred from '{self.name}' to '{other_warehouse.name}'")

    def reserve(self, item_id: str, n: int) -> None:
        """Reserve n units of an item. Raises ValueError if not enough available."""
        item = self.get_item(item_id)  # raises KeyError if not found
        if item.reserved + n > item.quantity:
            raise ValueError(
                f"Cannot reserve {n} units for item '{item_id}' in warehouse '{self.name}': "
                f"only {item.available()} available (reserved {item.reserved} of {item.quantity})."
            )
        item.reserved += n
        self._log.log("reserve", item_id,
                      f"Reserved {n} units in warehouse '{self.name}'")

    def low_stock(self, threshold: int) -> List[Item]:
        """Return a list of Items whose available() is below threshold,
        sorted by available() ascending."""
        low_items = [item for item in self._items.values() if item.available() < threshold]
        low_items.sort(key=lambda item: item.available())
        return low_items

    def to_json(self) -> str:
        """Serialize the warehouse to a JSON string containing its name
        and all items (using Item.to_dict())."""
        data = {
            "name": self.name,
            "items": [item.to_dict() for item in self._items.values()]
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, s: str, log: TransactionLog = None) -> 'Warehouse':
        """Reconstruct a Warehouse from a JSON string. If log is provided,
        it will be used; otherwise a new TransactionLog is created."""
        data = json.loads(s)
        warehouse = cls(name=data["name"], log=log)
        for item_dict in data["items"]:
            # Reconstruct Item from the dictionary (all fields are present)
            item = Item(
                id=item_dict["id"],
                sku=item_dict["sku"],
                name=item_dict["name"],
                quantity=item_dict["quantity"],
                unit_price=item_dict["unit_price"],
                reserved=item_dict["reserved"]
            )
            warehouse.add_item(item)
        return warehouse


if __name__ == "__main__":
    # Create a shared transaction log
    log = TransactionLog()

    # Create two warehouses
    wh1 = Warehouse("Warehouse 1", log=log)
    wh2 = Warehouse("Warehouse 2", log=log)

    # Add 3 items to Warehouse 1
    item1 = Item(sku="WIDGET", name="Widget", quantity=100, unit_price=2500)
    item2 = Item(sku="GADGET", name="Gadget", quantity=50, unit_price=1500)
    item3 = Item(sku="THING", name="Thingamajig", quantity=10, unit_price=500)
    wh1.add_item(item1)
    wh1.add_item(item2)
    wh1.add_item(item3)

    # Reserve some quantity of item1 and item2 in Warehouse 1
    wh1.reserve(item1.id, 20)
    wh1.reserve(item2.id, 10)

    # Transfer item3 from Warehouse 1 to Warehouse 2
    wh1.transfer(item3.id, wh2)

    # Print low stock items in Warehouse 1 with threshold 40
    low_stock_items = wh1.low_stock(40)
    print("Low stock items in Warehouse 1 (threshold 40):")
    for item in low_stock_items:
        print(f"  - {item.name}: available {item.available()}")

    # Dump Warehouse 1 to JSON and reload it
    wh1_json = wh1.to_json()
    print("\nWarehouse 1 JSON dump:")
    print(wh1_json)

    wh1_reloaded = Warehouse.from_json(wh1_json, log=log)

    # Print the transaction log entries
    print("\nTransaction Log Entries:")
    for entry in log.get_entries():
        timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry["timestamp"]))
        print(f"  [{timestamp_str}] {entry['action']}: {entry['detail']}")
