"""Store and serve what guide sites say about the phones VEXTRO lists.

A guide site names a phone its own way, so every page is first tied to a
catalog product. Nothing is created from one: a guide site lists thousands
of phones nobody sells any more, and a phone belongs in the catalog only
because a marketplace offers it.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.community_opinion import (
    CommunityOpinion,
    ProductCommunityRating,
)
from app.schemas.community_opinions import (
    SOURCE_NAMES,
    CommunityOpinionResponse,
    CommunityOpinionsIngestResponse,
    CommunityOpinionsInput,
    CommunitySourceResponse,
    ProductCommunityOpinionsResponse,
)
from app.services.cross_marketplace_matching import (
    cross_marketplace_product_key,
)
from app.services.opinion_risk_engine import (
    KIND_ABUSIVE,
    KIND_ADVERT,
    KIND_OPINION,
    KIND_QUESTION,
    OpinionEvidence,
    analyze_opinion,
)


logger = logging.getLogger(__name__)

# How many of a source's opinions a product page is given.
OPINIONS_PER_SOURCE = 60


def opinion_fingerprint(
    source: str,
    product_id: int,
    author: str | None,
    posted_at: datetime | None,
    text: str,
) -> str:
    """Identify one opinion so a later crawl does not store it again."""

    normalized_text = " ".join(text.casefold().split())
    parts = (
        source,
        str(product_id),
        " ".join((author or "").casefold().split()),
        posted_at.date().isoformat() if posted_at else "",
        normalized_text,
    )

    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


class CommunityOpinionService:
    def find_product(
        self,
        database_session: Session,
        payload: CommunityOpinionsInput,
    ) -> CanonicalProduct | None:
        """Return the catalog phone a guide-site page is about, if any."""

        for name in (payload.catalog_name, payload.product_name):
            if not name:
                continue

            exact = database_session.scalar(
                select(CanonicalProduct)
                .where(
                    CanonicalProduct.is_active.is_(True),
                    func.lower(CanonicalProduct.name) == name.strip().lower(),
                )
                .order_by(CanonicalProduct.id.asc())
                .limit(1)
            )
            if exact is not None:
                return exact

        if not payload.brand:
            return None

        # The same phone spelled another way ("Infinix Hot 70 Pro 5G"),
        # compared within its brand by the catalog's own identity key.
        brand = database_session.scalar(
            select(Brand).where(
                func.lower(Brand.name) == payload.brand.strip().lower()
            )
        )
        if brand is None:
            return None

        wanted = cross_marketplace_product_key(payload.product_name, brand.name)
        if not wanted:
            return None

        for candidate in database_session.scalars(
            select(CanonicalProduct)
            .where(
                CanonicalProduct.is_active.is_(True),
                CanonicalProduct.brand_id == brand.id,
            )
            .order_by(CanonicalProduct.id.asc())
        ):
            if cross_marketplace_product_key(candidate.name, brand.name) == wanted:
                return candidate

        return None

    def ingest(
        self,
        database_session: Session,
        payload: CommunityOpinionsInput,
    ) -> CommunityOpinionsIngestResponse:
        try:
            product = self.find_product(database_session, payload)

            if product is None:
                return CommunityOpinionsIngestResponse(
                    matched=False,
                    reason=(
                        "No catalog phone matches this page; guide-site "
                        "pages never create products."
                    ),
                )

            seen_at = payload.scraped_at or datetime.now(UTC)
            rating = database_session.scalar(
                select(ProductCommunityRating).where(
                    ProductCommunityRating.canonical_product_id == product.id,
                    ProductCommunityRating.source == payload.source,
                )
            )

            if rating is None:
                rating = ProductCommunityRating(
                    canonical_product_id=product.id,
                    source=payload.source,
                    source_product_name=payload.product_name,
                    source_url=payload.source_url,
                )
                database_session.add(rating)

            rating.source_product_name = payload.product_name
            rating.source_url = payload.source_url
            rating.opinions_url = payload.opinions_url or rating.opinions_url
            rating.rating = payload.rating
            rating.rating_count = payload.rating_count
            rating.reference_price = payload.reference_price
            rating.last_seen_at = seen_at

            fingerprints = {
                opinion_fingerprint(
                    payload.source,
                    product.id,
                    opinion.author,
                    opinion.posted_at,
                    opinion.text,
                ): opinion
                for opinion in payload.opinions
            }
            known = set(
                database_session.scalars(
                    select(CommunityOpinion.opinion_fingerprint).where(
                        CommunityOpinion.source == payload.source,
                        CommunityOpinion.opinion_fingerprint.in_(
                            list(fingerprints)
                        ),
                    )
                )
            ) if fingerprints else set()

            created = 0
            for fingerprint, opinion in fingerprints.items():
                if fingerprint in known:
                    continue

                database_session.add(
                    CommunityOpinion(
                        canonical_product_id=product.id,
                        source=payload.source,
                        opinion_fingerprint=fingerprint,
                        author_display_name=opinion.author,
                        posted_at=opinion.posted_at,
                        opinion_text=opinion.text,
                        contact_removed=opinion.contact_removed,
                        source_url=payload.opinions_url or payload.source_url,
                        source_position=opinion.position,
                        analysis_reasons=[],
                    )
                )
                created += 1

            # A new post can be a copy of an older one, so every post about
            # the phone is scored again, not only the ones just added.
            database_session.flush()
            self.score_product(database_session, product.id, payload.source)

            database_session.commit()

            return CommunityOpinionsIngestResponse(
                matched=True,
                canonical_product_id=product.id,
                product_name=product.name,
                created_count=created,
                duplicate_count=len(payload.opinions) - created,
            )
        except Exception:
            database_session.rollback()
            raise

    def score_product(
        self,
        database_session: Session,
        product_id: int,
        source: str,
    ) -> int:
        """Score every post one source holds about a phone; returns how many.

        The caller commits.
        """

        opinions = list(
            database_session.scalars(
                select(CommunityOpinion).where(
                    CommunityOpinion.canonical_product_id == product_id,
                    CommunityOpinion.source == source,
                )
            )
        )
        evidence = [
            OpinionEvidence(
                id=opinion.id,
                text=opinion.opinion_text,
                author=opinion.author_display_name,
                posted_at=opinion.posted_at,
                contact_removed=opinion.contact_removed,
            )
            for opinion in opinions
        ]

        for opinion, subject in zip(opinions, evidence):
            analysis = analyze_opinion(subject, evidence)
            opinion.analysis_version = analysis["analysis_version"]
            opinion.suspicion_score = analysis["suspicion_score"]
            opinion.suspicion_level = analysis["suspicion_level"]
            opinion.opinion_kind = analysis["opinion_kind"]
            opinion.analysis_reasons = analysis["reasons"]

        return len(opinions)

    def product_opinions(
        self,
        database_session: Session,
        product_id: int,
    ) -> ProductCommunityOpinionsResponse:
        ratings = list(
            database_session.scalars(
                select(ProductCommunityRating)
                .where(
                    ProductCommunityRating.canonical_product_id == product_id
                )
                .order_by(ProductCommunityRating.source.asc())
            )
        )

        sources: list[CommunitySourceResponse] = []
        for rating in ratings:
            filters = (
                CommunityOpinion.canonical_product_id == product_id,
                CommunityOpinion.source == rating.source,
            )
            kind_counts = {
                kind: count
                for kind, count in database_session.execute(
                    select(
                        CommunityOpinion.opinion_kind,
                        func.count(CommunityOpinion.id),
                    )
                    .where(*filters)
                    .group_by(CommunityOpinion.opinion_kind)
                )
            }
            opinion_count = sum(kind_counts.values())
            # Abuse is kept as evidence but never served to a reader.
            opinions = database_session.scalars(
                select(CommunityOpinion)
                .where(
                    *filters,
                    CommunityOpinion.opinion_kind.is_distinct_from(
                        KIND_ABUSIVE
                    ),
                )
                .order_by(
                    CommunityOpinion.posted_at.desc().nulls_last(),
                    CommunityOpinion.id.desc(),
                )
                .limit(OPINIONS_PER_SOURCE)
            )

            sources.append(
                CommunitySourceResponse(
                    source=rating.source,
                    source_name=SOURCE_NAMES.get(rating.source, rating.source),
                    source_url=rating.source_url,
                    opinions_url=rating.opinions_url,
                    rating=rating.rating,
                    rating_count=rating.rating_count,
                    reference_price=rating.reference_price,
                    last_seen_at=rating.last_seen_at,
                    opinion_count=opinion_count,
                    genuine_opinion_count=kind_counts.get(KIND_OPINION, 0),
                    advert_count=kind_counts.get(KIND_ADVERT, 0),
                    question_count=kind_counts.get(KIND_QUESTION, 0),
                    hidden_count=kind_counts.get(KIND_ABUSIVE, 0),
                    opinions=[
                        CommunityOpinionResponse.model_validate(opinion)
                        for opinion in opinions
                    ],
                )
            )

        return ProductCommunityOpinionsResponse(
            product_id=product_id,
            sources=sources,
        )


community_opinion_service = CommunityOpinionService()

__all__ = [
    "CommunityOpinionService",
    "community_opinion_service",
    "opinion_fingerprint",
]
