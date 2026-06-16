# inventory.py

from dataclasses import dataclass, field
from uuid import uuid4
from typing import Dict, List, Optional
import time
import json


@dataclass
class Item:
    id: str = field(default_factory=lambda: str(uuid4()))
    sku: str = ""
    name: str = ""
    quantity: int = 0
    unit_price: int = 0  # stored in cents
    reserved: int = 0  # units reserved but not yet shipped

    def total_value(self) -> int:
        """Return the total value of this item in cents (quantity * unit_price)."""
        return self.quantity * self.unit_price

    def available(self) -> int:
        """Return the number of units available (not reserved)."""
        return self.quantity - self.reserved

    def to_dict(self) -> dict:
        """Serialize item to dict using exact field names plus derived 'available'."""
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
    """Records all warehouse transactions."""

    def __init__(self):
        self._entries: List[Dict] = []

    def append(self, action: str, item_id: str, detail: str = "") -> None:
        """Append a transaction record."""
        self._entries.append({
            "action": action,
            "item_id": item_id,
            "timestamp": time.time(),
            "detail": detail
        })

    def get_entries(self) -> List[Dict]:
        """Return a copy of all entries."""
        return list(self._entries)


class Warehouse:
    """A warehouse that holds items keyed by their id."""

    def __init__(self, name: str = "", log: Optional[TransactionLog] = None):
        self.name = name
        self._items: Dict[str, Item] = {}
        self._log = log if log is not None else TransactionLog()

    def add_item(self, item: Item) -> None:
        """Add an item to the warehouse."""
        self._items[item.id] = item
        self._log.append("add_item", item.id, f"Added item {item.sku}")

    def remove_item(self, item_id: str) -> None:
        """Remove an item by its id. Raises KeyError if not found."""
        if item_id not in self._items:
            raise KeyError(f"Item with id '{item_id}' not found.")
        del self._items[item_id]
        self._log.append("remove_item", item_id, f"Removed item")

    def get_item(self, item_id: str) -> Item:
        """Get an item by its id. Raises KeyError if not found."""
        if item_id not in self._items:
            raise KeyError(f"Item with id '{item_id}' not found.")
        return self._items[item_id]

    def transfer(self, item_id: str, other_warehouse: 'Warehouse') -> None:
        """Move an item from this warehouse to another warehouse."""
        item = self.get_item(item_id)
        self.remove_item(item_id)
        other_warehouse.add_item(item)
        self._log.append("transfer", item_id, f"Transferred from {self.name} to {other_warehouse.name}")

    def reserve(self, item_id: str, n: int) -> None:
        """Reserve n units of an item. Raises ValueError if n would exceed available quantity."""
        item = self.get_item(item_id)
        if n > item.available():
            raise ValueError(
                f"Cannot reserve {n} units; only {item.available()} available "
                f"(quantity={item.quantity}, reserved={item.reserved})."
            )
        item.reserved += n
        self._log.append("reserve", item_id, f"Reserved {n} units")

    def low_stock(self, threshold: int) -> List[Item]:
        """Return items whose available() is below threshold, sorted by available() ascending."""
        low_items = [item for item in self._items.values() if item.available() < threshold]
        low_items.sort(key=lambda item: item.available())
        return low_items

    def to_json(self) -> str:
        """Return a JSON string of all items and the warehouse name."""
        data = {
            "name": self.name,
            "items": [item.to_dict() for item in self._items.values()]
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, s: str, log: Optional[TransactionLog] = None) -> 'Warehouse':
        """Reconstruct a Warehouse from a JSON string, optionally using a shared TransactionLog."""
        data = json.loads(s)
        warehouse = cls(name=data["name"], log=log)
        for item_data in data["items"]:
            item = Item(
                id=item_data["id"],
                sku=item_data["sku"],
                name=item_data["name"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                reserved=item_data["reserved"]
            )
            warehouse.add_item(item)
        return warehouse


if __name__ == "__main__":
    # Create a shared transaction log
    log = TransactionLog()

    # Create two warehouses
    wh1 = Warehouse("Main Warehouse", log=log)
    wh2 = Warehouse("Secondary Warehouse", log=log)

    # Add 3 items
    item1 = Item(sku="SKU001", name="Widget A", quantity=100, unit_price=500)
    item2 = Item(sku="SKU002", name="Widget B", quantity=50, unit_price=750)
    item3 = Item(sku="SKU003", name="Widget C", quantity=200, unit_price=300)

    wh1.add_item(item1)
    wh1.add_item(item2)
    wh1.add_item(item3)

    # Reserve some
    wh1.reserve(item1.id, 10)
    wh1.reserve(item2.id, 5)

    # Transfer one item between warehouses
    wh1.transfer(item3.id, wh2)

    # Print low_stock (threshold 80)
    print("Low stock items (threshold 80):")
    for item in wh1.low_stock(80):
        print(f"  {item.sku}: {item.available()} available")

    # Dump wh1 to JSON and reload via from_json
    json_str = wh1.to_json()
    print(f"\nWarehouse 1 JSON:\n{json_str}")

    # Reload using a new log (or None to use default)
    wh1_reloaded = Warehouse.from_json(json_str)
    print(f"\nReloaded warehouse: {wh1_reloaded.name}")
    for item in wh1_reloaded._items.values():
        print(f"  {item.sku}: {item.quantity} units @ {item.unit_price} cents")

    # Print the transaction log
    print("\nTransaction log:")
    for entry in log.get_entries():
        print(f"  {entry['action']}: {entry['item_id']} at {entry['timestamp']:.2f} - {entry['detail']}")
