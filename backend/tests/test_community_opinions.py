"""Community ratings and opinions from guide sites."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.canonical_product import CanonicalProduct
from app.models.community_opinion import (
    CommunityOpinion,
    ProductCommunityRating,
)
from tests.test_smartphone_sync import (  # noqa: F401 - shared fixtures
    configure_ingestion_key,
    headers,
    sync_context,
)


INGEST_ENDPOINT = "/api/v1/internal/acquisition/community-opinions"
RUNS_ENDPOINT = "/api/v1/internal/acquisition/runs"


def page(context: dict[str, object], **overrides: object) -> dict[str, object]:
    """A WhatMobile page for the phone the fixture created."""

    payload: dict[str, object] = {
        "source": "whatmobile",
        "product_name": context["product_name"],
        "catalog_name": context["product_name"],
        "brand": "Samsung",
        "source_url": f"https://www.whatmobile.com.pk/Samsung_Sync-{context['token']}",
        "opinions_url": (
            f"https://www.whatmobile.com.pk/Samsung_Sync-{context['token']}_Reviews_0"
        ),
        "rating": 2.8,
        "rating_count": 22,
        "reference_price": 89999,
        "scraped_at": "2026-10-10T18:00:00Z",
        "opinions": [
            {
                "position": 1,
                "author": "visitor1",
                "posted_at": "2026-09-18T00:00:00Z",
                "text": "IPS display in this expensive phone.",
            },
            {
                "position": 2,
                "author": "visitor2",
                "posted_at": "2026-09-10T00:00:00Z",
                "text": "Sale karna hai rabta [number removed]",
                "contact_removed": True,
            },
        ],
    }
    payload.update(overrides)

    return payload


def ingest(client: TestClient, payload: dict[str, object]) -> dict[str, object]:
    response = client.post(INGEST_ENDPOINT, headers=headers(), json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def read(client: TestClient, product_id: int) -> dict[str, object]:
    response = client.get(f"/api/v1/products/{product_id}/community-opinions")
    assert response.status_code == 200, response.text
    return response.json()


def test_a_guide_site_page_is_stored_against_the_phone_it_names(
    client: TestClient,
    sync_context: dict[str, object],
) -> None:
    result = ingest(client, page(sync_context))

    assert result["matched"] is True
    assert result["canonical_product_id"] == sync_context["product_id"]
    assert result["created_count"] == 2
    assert result["duplicate_count"] == 0

    body = read(client, int(sync_context["product_id"]))
    assert len(body["sources"]) == 1

    source = body["sources"][0]
    assert source["source"] == "whatmobile"
    assert source["source_name"] == "WhatMobile"
    assert float(source["rating"]) == 2.8
    assert source["rating_count"] == 22
    assert float(source["reference_price"]) == 89999
    assert source["opinion_count"] == 2
    # Newest first.
    assert [opinion["author_display_name"] for opinion in source["opinions"]] == [
        "visitor1",
        "visitor2",
    ]
    assert source["opinions"][1]["contact_removed"] is True


def test_stored_posts_are_scored_and_counted_by_kind(
    client: TestClient,
    sync_context: dict[str, object],
) -> None:
    payload = page(sync_context)
    payload["opinions"] = [
        *payload["opinions"],
        {
            "position": 3,
            "author": "visitor3",
            "posted_at": "2026-09-01T00:00:00Z",
            "text": "pakistan me kb aye ga",
        },
    ]
    ingest(client, payload)

    source = read(client, int(sync_context["product_id"]))["sources"][0]

    assert source["opinion_count"] == 3
    assert source["genuine_opinion_count"] == 1
    assert source["advert_count"] == 1
    assert source["question_count"] == 1

    view, advert, question = source["opinions"]
    assert view["opinion_kind"] == "opinion"
    assert view["suspicion_level"] == "low"
    assert advert["opinion_kind"] == "advert"
    assert advert["suspicion_level"] == "high"
    assert advert["suspicion_score"] == 70
    assert len(advert["analysis_reasons"]) == 2
    assert question["opinion_kind"] == "question"


def test_a_copy_arriving_in_a_later_crawl_rescored_the_older_post(
    client: TestClient,
    sync_context: dict[str, object],
) -> None:
    """Scores depend on the other posts, so old posts are scored again."""

    ingest(client, page(sync_context))
    product_id = int(sync_context["product_id"])
    assert read(client, product_id)["sources"][0]["opinions"][0][
        "suspicion_score"
    ] == 0

    later = page(sync_context)
    later["opinions"] = [
        {
            "position": 1,
            "author": "visitor9",
            "posted_at": "2026-10-09T00:00:00Z",
            "text": "IPS display in this expensive phone.",
        },
    ]
    ingest(client, later)

    opinions = read(client, product_id)["sources"][0]["opinions"]
    copies = [
        opinion
        for opinion in opinions
        if opinion["opinion_text"] == "IPS display in this expensive phone."
    ]
    assert len(copies) == 2
    assert all(copy["suspicion_score"] == 40 for copy in copies)


def test_a_second_crawl_adds_only_the_opinions_it_has_not_seen(
    client: TestClient,
    database_session: Session,
    sync_context: dict[str, object],
) -> None:
    ingest(client, page(sync_context))

    later = page(sync_context, rating=3.1, rating_count=23)
    later["opinions"] = [
        *later["opinions"],
        {
            "position": 3,
            "author": "visitor3",
            "posted_at": "2026-10-09T00:00:00Z",
            "text": "Battery acha hai lekin camera kamzor.",
        },
    ]
    result = ingest(client, later)

    assert result["created_count"] == 1
    assert result["duplicate_count"] == 2

    product_id = int(sync_context["product_id"])
    assert database_session.scalar(
        select(func.count(CommunityOpinion.id)).where(
            CommunityOpinion.canonical_product_id == product_id
        )
    ) == 3

    # One rating row per phone and source, carrying the latest figures.
    ratings = list(
        database_session.scalars(
            select(ProductCommunityRating).where(
                ProductCommunityRating.canonical_product_id == product_id
            )
        )
    )
    assert len(ratings) == 1
    assert float(ratings[0].rating) == 3.1
    assert ratings[0].rating_count == 23


def test_a_phone_spelled_differently_is_still_recognised_within_its_brand(
    client: TestClient,
    sync_context: dict[str, object],
) -> None:
    result = ingest(
        client,
        page(
            sync_context,
            catalog_name=None,
            product_name=f"{sync_context['product_name']} 5G",
        ),
    )

    assert result["matched"] is True
    assert result["canonical_product_id"] == sync_context["product_id"]


def test_a_page_for_an_unlisted_phone_stores_nothing_and_creates_no_product(
    client: TestClient,
    database_session: Session,
    sync_context: dict[str, object],
) -> None:
    """Guide sites list thousands of phones nobody sells any more."""

    products_before = database_session.scalar(
        select(func.count(CanonicalProduct.id))
    )
    result = ingest(
        client,
        page(
            sync_context,
            catalog_name="Samsung Phone Nobody Lists 9000",
            product_name="Samsung Phone Nobody Lists 9000",
        ),
    )

    assert result["matched"] is False
    assert result["created_count"] == 0
    database_session.expire_all()
    assert database_session.scalar(
        select(func.count(CanonicalProduct.id))
    ) == products_before
    assert read(client, int(sync_context["product_id"]))["sources"] == []


def test_opinions_are_accepted_only_from_the_crawler(
    client: TestClient,
    sync_context: dict[str, object],
) -> None:
    response = client.post(INGEST_ENDPOINT, json=page(sync_context))

    assert response.status_code in {401, 403}


def test_a_phone_without_opinions_reports_no_sources(
    client: TestClient,
    sync_context: dict[str, object],
) -> None:
    assert read(client, int(sync_context["product_id"])) == {
        "product_id": sync_context["product_id"],
        "sources": [],
    }


def test_a_guide_site_crawl_is_tracked_like_a_marketplace_crawl(
    client: TestClient,
) -> None:
    response = client.post(
        RUNS_ENDPOINT,
        headers=headers(),
        json={
            "platform": "whatmobile",
            "spider_name": "whatmobile_opinions",
            "trigger_type": "test",
            "parser_version": "whatmobile-v1-opinions",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["platform"] == "whatmobile"
