"""Live clone and generator adapters for the content-vector known-item eval."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .autogen_eval import CorpusNode

_TOKEN = re.compile(r"[a-z0-9]+")


def normalized_tokens(text: str) -> frozenset[str]:
    return frozenset(_TOKEN.findall(text.lower()))


@dataclass
class Neo4jCorpusReader:
    """Read eligible semantic memories and form lane-neutral lexical clusters."""

    driver: Any
    _nodes: list[CorpusNode] | None = field(default=None, init=False)
    _tokens: dict[str, frozenset[str]] = field(default_factory=dict, init=False)

    def sample_candidates(self) -> list[CorpusNode]:
        if self._nodes is None:
            with self.driver.session() as session:
                rows = session.run(
                    """
                    MATCH (n:Entity)
                    WHERE n.name_embedding IS NOT NULL
                      AND coalesce(n.structure_role, '') = ''
                    RETURN n.uuid AS uuid, n.name AS name, n.summary AS summary,
                           n.content AS content, coalesce(n.namespace, 'default') AS namespace
                    ORDER BY n.uuid
                    """
                ).data()
            self._nodes = []
            for row in rows:
                text = next(
                    (str(row[key]).strip() for key in ("summary", "content", "name")
                     if row.get(key) and str(row[key]).strip()),
                    "",
                )
                if text:
                    node = CorpusNode(
                        uuid=str(row["uuid"]),
                        name=str(row.get("name") or ""),
                        text=text,
                        namespace=str(row.get("namespace") or "default"),
                    )
                    self._nodes.append(node)
                    self._tokens[node.uuid] = normalized_tokens(text)
        return list(self._nodes)

    def duplicate_cluster(self, node: CorpusNode, threshold: float) -> list[str]:
        nodes = self.sample_candidates()
        wanted = self._tokens[node.uuid]
        if not wanted:
            return []
        siblings: list[str] = []
        for candidate in nodes:
            if candidate.uuid == node.uuid:
                continue
            other = self._tokens[candidate.uuid]
            union = wanted | other
            similarity = len(wanted & other) / len(union) if union else 0.0
            if similarity >= threshold:
                siblings.append(candidate.uuid)
        return siblings


@dataclass
class OpenAIQueryGenerator:
    """Generate paraphrases with a chat model distinct from the embedding model."""

    client: Any
    model: str

    def generate(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0.4,
            max_output_tokens=80,
        )
        return str(response.output_text or "").strip()
