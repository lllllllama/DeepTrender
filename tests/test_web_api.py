"""Web API integration tests."""

import json


class TestHealthEndpoint:

    def test_health_check(self, test_client):
        response = test_client.get("/api/health")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert data["service"] == "deeptrender"


class TestOverviewEndpoint:

    def test_overview(self, test_client):
        response = test_client.get("/api/stats/overview")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "total_papers" in data
        assert "total_keywords" in data
        assert "total_venues" in data
        assert "venues" in data
        assert "years" in data
        assert isinstance(data["venues"], list)
        assert isinstance(data["years"], list)
        assert isinstance(data["total_keywords"], int)

    def test_overview_empty_dataset_contract(self, test_client):
        response = test_client.get("/api/stats/overview")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "year_range" in data
        assert "total_papers" in data
        assert "total_keywords" in data
        assert data["total_papers"] >= 0


class TestKeywordsEndpoints:

    def test_top_keywords(self, test_client):
        response = test_client.get("/api/keywords/top")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_top_keywords_with_limit(self, test_client):
        response = test_client.get("/api/keywords/top?limit=10")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) <= 10

    def test_top_keywords_with_venue(self, test_client):
        response = test_client.get("/api/keywords/top?venue=ICLR")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_keyword_trends(self, test_client):
        response = test_client.get("/api/keywords/trends")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_keyword_trends_with_keywords(self, test_client):
        response = test_client.get("/api/keywords/trends?keyword=transformer&keyword=bert")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_wordcloud(self, test_client):
        response = test_client.get("/api/keywords/wordcloud")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)
        for item in data:
            if item:
                assert "name" in item
                assert "value" in item

    def test_emerging_keywords(self, test_client):
        response = test_client.get("/api/keywords/emerging")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)


class TestVenuesEndpoints:

    def test_venues_list(self, test_client):
        response = test_client.get("/api/stats/venues")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_venue_detail(self, test_client):
        response = test_client.get("/api/stats/venue/ICLR")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "venue" in data
        assert data["venue"] == "ICLR"


class TestComparisonEndpoint:

    def test_comparison(self, test_client):
        response = test_client.get("/api/keywords/comparison")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "year" in data
        assert "venues" in data


class TestStatusEndpoint:

    def test_status(self, test_client):
        response = test_client.get("/api/status")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "database" in data
        assert "data" in data
        assert "server_time" in data

    def test_refresh(self, test_client):
        response = test_client.post("/api/refresh")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "success"
        assert "database_path" in data
        assert "total_papers" in data


class TestV01FrontendApi:

    def assert_contract(self, data):
        assert set(data.keys()) == {"data", "meta", "warnings", "evidence"}
        assert "taxonomy_version" in data["meta"]
        assert "data_policy_version" in data["meta"]
        assert "generated_at" in data["meta"]
        assert "source_layer" in data["meta"]
        assert "limit" in data["meta"]
        assert "offset" in data["meta"]
        assert "has_more" in data["meta"]
        assert isinstance(data["warnings"], list)
        assert isinstance(data["evidence"], list)

    def test_v01_overview_contract(self, test_client):
        response = test_client.get("/api/v01/overview")
        assert response.status_code == 200
        data = json.loads(response.data)
        self.assert_contract(data)
        assert "normalized_query" in data["data"]
        assert "total_papers" in data["data"]

    def test_v01_domains_contract(self, test_client):
        response = test_client.get("/api/v01/domains")
        assert response.status_code == 200
        data = json.loads(response.data)
        self.assert_contract(data)
        assert "domains" in data["data"]

    def test_v01_data_quality_contract(self, test_client):
        response = test_client.get("/api/v01/data-quality?venue=ICLR&year=2024")
        assert response.status_code == 200
        data = json.loads(response.data)
        self.assert_contract(data)
        assert "metrics" in data["data"]

    def test_v01_venue_year_topic_contract(self, test_client):
        response = test_client.get("/api/v01/venue-year-topic?venue=ICLR&year=2024&topic=transformer")
        assert response.status_code == 200
        data = json.loads(response.data)
        self.assert_contract(data)
        assert "normalized_query" in data["data"]
        assert "relative_frequency" in data["data"]
        assert "matched_papers" in data["data"]

    def test_v01_venue_year_topic_requires_query(self, test_client):
        response = test_client.get("/api/v01/venue-year-topic?venue=ICLR")
        assert response.status_code == 400

    def test_legacy_routes_still_work(self, test_client):
        assert test_client.get("/api/stats/overview").status_code == 200
        assert test_client.get("/api/status").status_code == 200
        assert test_client.get("/api/stats/venues").status_code == 200


class TestApiParameterBounds:

    def test_arxiv_papers_limit_and_offset_are_bounded(self, test_client):
        from web.app import MAX_API_LIMIT

        response = test_client.get("/api/arxiv/papers?limit=999999&offset=-10")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["limit"] == MAX_API_LIMIT
        assert data["offset"] == 0

    def test_v01_limit_and_offset_are_bounded(self, test_client):
        from web.app import MAX_API_LIMIT

        response = test_client.get("/api/v01/domains?limit=999999&offset=-10")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["meta"]["limit"] == MAX_API_LIMIT
        assert data["meta"]["offset"] == 0

    def test_run_server_defaults_are_local_and_non_debug(self):
        import inspect
        from web.app import run_server

        signature = inspect.signature(run_server)
        assert signature.parameters["host"].default == "127.0.0.1"
        assert signature.parameters["debug"].default is False

class TestStaticFiles:

    def test_index_page(self, test_client):
        response = test_client.get("/")
        assert response.status_code == 200
