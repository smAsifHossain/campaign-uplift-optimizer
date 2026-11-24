from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path


class IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del tag
        for name, value in attrs:
            if name == "id" and value:
                self.ids.append(value)


def test_deployed_result_is_real_data_and_matches_canonical_artifact() -> None:
    artifact = json.loads(Path("artifacts/results.json").read_text(encoding="utf-8"))
    deployed = json.loads(Path("site/data/results.json").read_text(encoding="utf-8"))
    assert deployed == artifact
    assert deployed["status"] == "portfolio_real_data"
    assert deployed["source"]["raw_data_committed"] is False


def test_site_has_unique_element_ids() -> None:
    parser = IdCollector()
    parser.feed(Path("site/index.html").read_text(encoding="utf-8"))
    assert len(parser.ids) == len(set(parser.ids))


def test_pages_workflow_uses_artifact_deployment_not_bot_commits() -> None:
    workflow = Path(".github/workflows/pages.yml").read_text(encoding="utf-8")
    assert "actions/upload-pages-artifact" in workflow
    assert "actions/deploy-pages" in workflow
    assert "git push" not in workflow


def test_site_is_a_compact_single_page_with_data_method_and_theme_switching() -> None:
    html = Path("site/index.html").read_text(encoding="utf-8")
    css = Path("site/styles.css").read_text(encoding="utf-8")
    javascript = Path("site/app.js").read_text(encoding="utf-8")

    assert 'id="evidence"' in html
    assert 'id="simulator"' in html
    assert 'id="method"' in html
    assert "Criteo Uplift Prediction v2.1" in html
    assert 'class="method-table"' in html
    assert "Data preparation" in html
    assert "Experiment analysis" in html
    assert "Uplift modeling" in html
    assert "Limitations and guardrails" not in html
    assert "limitations-list" not in html
    assert "Honest result" not in html
    assert "summary-band" not in html
    assert "<details>" not in html
    assert 'data-page=' not in html
    assert 'class="view"' not in html
    assert "split-train-rows" in html
    assert "theme-toggle" in html
    assert "theme-track" in html
    assert "effect-chart" in html
    assert "model-chart" in html
    assert "policy-chart" in html
    assert "optimizer-chart" in html
    assert "https://www.linkedin.com/in/smasifhossain" in html
    assert 'html[data-theme="dark"]' in css
    assert "campaign-uplift-theme" in javascript
    assert "renderEffectChart" in javascript
    assert "renderModelChart" in javascript
    assert "renderPolicyChart" in javascript
