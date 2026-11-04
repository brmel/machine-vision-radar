from __future__ import annotations

from typing import Protocol, Sequence

from radar.domain.model.entities import CategoryPage, HistoryView, IndexView, MarketView, ProductCard, ProductView

class CatalogRepository(Protocol):
    def index(self) -> IndexView:
        ...

    def product(self, key: str) -> ProductView | None:
        ...

    def products(self, ids: Sequence[str]) -> list[ProductView]:
        ...

    def category_page(self, category: str, cursor: str | None = None) -> CategoryPage | None:
        ...

    def users(self, product: str) -> list[ProductCard]:
        ...

    def history(self, entity: str) -> HistoryView | None:
        ...

    def market(self) -> MarketView:
        ...
