"""HTTP client for the Stratova FastAPI backend."""

import os

import httpx

DEFAULT_API_URL = os.getenv("STRATOVA_API_URL", "http://127.0.0.1:8000")


class StratovaAPI:
    def __init__(self, base_url: str = DEFAULT_API_URL):
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/health")
            resp.raise_for_status()
            return resp.json()

    def get_agents(self) -> list[str]:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/agents")
            resp.raise_for_status()
            return resp.json()

    def get_default_client(self) -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/client/default")
            resp.raise_for_status()
            return resp.json()

    def get_reports(self, company: str = "Beam Data") -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/reports", params={"company": company})
            resp.raise_for_status()
            return resp.json()

    def get_research_text(self, company: str = "Beam Data") -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/research/text", params={"company": company})
            resp.raise_for_status()
            return resp.json()

    def get_research_json(self, company: str = "Beam Data") -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/research/json", params={"company": company})
            resp.raise_for_status()
            return resp.json()

    def get_strategy_text(self, company: str = "Beam Data") -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/strategy/text", params={"company": company})
            resp.raise_for_status()
            return resp.json()

    def get_strategy_json(self, company: str = "Beam Data") -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/strategy/json", params={"company": company})
            resp.raise_for_status()
            return resp.json()

    def run_orca(self, gtm_query: dict | None = None, background: bool = False) -> dict:
        payload = gtm_query or {}
        with httpx.Client(timeout=600) as client:
            resp = client.post(
                f"{self.base_url}/orca/run",
                json=payload,
                params={"background": background},
            )
            resp.raise_for_status()
            return resp.json()

    def run_research(self, client_config: dict | None = None, background: bool = False) -> dict:
        payload = client_config or {}
        with httpx.Client(timeout=600) as client:
            resp = client.post(
                f"{self.base_url}/research/run",
                json=payload or None,
                params={"background": background},
            )
            resp.raise_for_status()
            return resp.json()

    def run_strategy(self, client_config: dict | None = None, background: bool = False) -> dict:
        payload = client_config or {}
        with httpx.Client(timeout=600) as client:
            resp = client.post(
                f"{self.base_url}/strategy/run",
                json=payload or None,
                params={"background": background},
            )
            resp.raise_for_status()
            return resp.json()

    def get_content_text(self, company: str = "Beam Data") -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/content/text", params={"company": company})
            resp.raise_for_status()
            return resp.json()

    def get_content_json(self, company: str = "Beam Data") -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/content/json", params={"company": company})
            resp.raise_for_status()
            return resp.json()

    def run_content(
        self,
        client_config: dict | None = None,
        generate_images: bool = True,
        posts_per_platform: int = 3,
        blog_count: int = 2,
        email_sequence_length: int = 3,
        background: bool = False,
    ) -> dict:
        payload = {
            "client": client_config,
            "generate_images": generate_images,
            "posts_per_platform": posts_per_platform,
            "blog_count": blog_count,
            "email_sequence_length": email_sequence_length,
        }
        with httpx.Client(timeout=900) as client:
            resp = client.post(
                f"{self.base_url}/content/run",
                json=payload,
                params={"background": background},
            )
            resp.raise_for_status()
            return resp.json()

    def get_brand_text(self, company: str = "Beam Data") -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/brand/text", params={"company": company})
            resp.raise_for_status()
            return resp.json()

    def get_brand_json(self, company: str = "Beam Data") -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/brand/json", params={"company": company})
            resp.raise_for_status()
            return resp.json()

    def get_brand_identity(self) -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/brand/identity")
            resp.raise_for_status()
            return resp.json()

    def run_brand(self, client_config: dict | None = None, background: bool = False) -> dict:
        payload = client_config or {}
        with httpx.Client(timeout=900) as client:
            resp = client.post(
                f"{self.base_url}/brand/run",
                json=payload or None,
                params={"background": background},
            )
            resp.raise_for_status()
            return resp.json()

    def job_status(self) -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/jobs/status")
            resp.raise_for_status()
            return resp.json()
