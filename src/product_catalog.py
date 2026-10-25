"""Explicit source assignments for the two prepared Patagonia demo products."""
from dataclasses import dataclass

DEFAULT_PRODUCT_ID = "nano_puff_84212"

@dataclass(frozen=True)
class DemoProduct:
    product_id: str
    name: str
    style: str
    facts_source: str
    source_ids: frozenset[str]
    brief: str
    focus: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"{self.name} · Style {self.style}"

    @property
    def scope(self) -> str:
        return f"{self.label} · US · English"

PRODUCTS = {
    DEFAULT_PRODUCT_ID: DemoProduct(
        DEFAULT_PRODUCT_ID, "Men's Nano Puff Jacket", "84212",
        "knowledge_base/primary/product_facts.md",
        frozenset({"knowledge_base/primary/product_facts.md", "knowledge_base/primary/brand_voice.md",
                   "knowledge_base/primary/repair_and_reuse.md", "knowledge_base/primary/past_content/examples.md",
                   "knowledge_base/secondary/competitor_context.md", "knowledge_base/secondary/market_trends.md"}),
        "Introduce Patagonia's Men's Nano Puff Jacket, style 84212, to an English-speaking US audience planning everyday "
        "outings and outdoor trips. Highlight verified packability and practical features. Use a direct, useful tone and "
        "one invitation to explore the product details. Avoid prices, discounts, urgency and unsupported environmental claims.",
        ("Use the verified lightweight, compressible construction and chest-pocket stuffsack.",
         "Use water-resistant wording; do not call this insulated jacket waterproof."),
    ),
    "torrentshell_85241": DemoProduct(
        "torrentshell_85241", "Men's Torrentshell 3L Rain Jacket", "85241",
        "knowledge_base/primary/torrentshell_85241.md",
        frozenset({"knowledge_base/primary/torrentshell_85241.md"}),
        "Introduce Patagonia's Men's Torrentshell 3L Rain Jacket, style 85241, to an English-speaking US audience "
        "planning rainy everyday outings. Highlight the verified three-layer rain shell, adjustable hood, pit zips "
        "and left-handwarmer-pocket storage. Use a direct, useful tone and one invitation to explore product details. "
        "Avoid prices, discounts, urgency, unverified insulation claims and unsupported environmental claims.",
        ("Use the sourced three-layer rain shell, adjustable hood, pit zips and left-pocket storage.",
         "Do not import Nano Puff insulation, chest-pocket storage or care instructions."),
    ),
}

def get_product(product_id: str) -> DemoProduct:
    try:
        return PRODUCTS[product_id]
    except (KeyError, TypeError) as exc:
        raise ValueError("Unknown prepared product.") from exc
