"""Render detached comparison reports without active content, IO or factual drift."""

import builtins
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from equiframe.comparison_types import ComparisonValue
from equiframe.errors import ResourceLimitError
from equiframe.report_rendering import (
    render_comparison_html,
    render_comparison_notebook,
    render_comparison_text,
)
from equiframe.report_types import (
    ComparisonReport,
    ReportCount,
    ReportEvidenceManifest,
    ReportPolicy,
    ReportValue,
    ReportViewPolicy,
    ReportWitness,
)

RENDERERS = (render_comparison_text, render_comparison_html, render_comparison_notebook)


def value(text='"café 雪"', *, disclosure="visible", native="string", physical="large_string"):
    return ReportValue(
        disclosure=disclosure,
        kind="string",
        representation=text if disclosure == "visible" else f"[{disclosure}]",
        native_type=native,
        physical_type=physical,
        value=ComparisonValue(kind="string", value="café 雪") if disclosure == "visible" else None,
    )


def report(*, state="different", complete=True, reference="expected", values=None):
    values = (value(),) if values is None else values
    witness = ReportWitness(
        category="content",
        code="cell_mismatch",
        reason="Values differ under the declared exact policy",
        position=0,
        other_position=1,
        column="amount",
        columns=("amount",),
        key_columns=("account",),
        key=(value('"account A"'),),
        candidate=values,
        reference=(value('"reference value"'),),
        candidate_count=1,
        reference_count=1,
    )
    examples = () if state == "equivalent" else (witness,)
    return ComparisonReport(
        state=state,
        complete=complete,
        reference=reference,
        strategy="key",
        coverage="complete" if complete else "partial",
        contract_sha256="a" * 64,
        spec_sha256="b" * 64,
        counts=(
            ReportCount(
                name="candidate_rows",
                value=12,
                precision="exact" if complete else "lower_bound",
                unit="rows",
            ),
            ReportCount(
                name="reference_rows",
                value=12,
                precision="exact" if complete else "lower_bound",
                unit="rows",
            ),
            ReportCount(
                name="matched_rows",
                value=12 if state == "equivalent" else 10,
                precision="exact" if state == "equivalent" else "estimate",
                unit="rows",
            ),
            ReportCount(
                name="difference_records",
                value=0 if state == "equivalent" else 2,
                precision="exact" if complete else "lower_bound",
                unit="records",
            ),
            ReportCount(
                name="contract_violations",
                value=0,
                precision="exact" if complete else "lower_bound",
                unit="records",
            ),
            ReportCount(name="added_rows", value=None, precision="unknown", unit="rows"),
            ReportCount(name="removed_rows", value=None, precision="unknown", unit="rows"),
            ReportCount(
                name="modified_rows",
                value=0 if state == "equivalent" else 1,
                precision="exact" if complete else "lower_bound",
                unit="rows",
            ),
            ReportCount(
                name="candidate_excess_occurrences",
                value=None,
                precision="unknown",
                unit="occurrences",
            ),
            ReportCount(
                name="reference_excess_occurrences",
                value=None,
                precision="unknown",
                unit="occurrences",
            ),
        ),
        reasons=() if state == "equivalent" else ("Captured values differ",),
        next_action="Review the preserved evidence before accepting the output",
        policies=(ReportPolicy(name="Numeric comparison", value="exact; no tolerance"),),
        examples=examples,
        evidence=ReportEvidenceManifest(
            mode="detail",
            inspection="result_only",
            evaluation_complete=complete,
            counts_final=complete,
            available_records=0 if state == "equivalent" else 2,
            included_examples=len(examples),
            display_complete=not examples,
            values_withheld=False,
            metadata_withheld=False,
            required_exhaustive=False,
            acceptance="satisfied",
            unmet_requirements=(),
            reproduction="not_requested",
        ),
        options=ReportViewPolicy(
            mode="detail",
            include_values=True,
            include_metadata=True,
            redacted_column_count=0,
            max_examples=20,
            max_value_chars=4096,
            max_report_bytes=2 * 1024 * 1024,
            require_exhaustive=False,
        ),
    )


class ParsedHTML(HTMLParser):
    def __init__(self, document):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.attributes = []
        self.text = []
        self.hidden = 0
        self.feed(document)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)
        if tag in {"head", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"head", "style"}:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data:
            self.text.append(data)


def with_budget(source, limit):
    return source.model_copy(
        update={"options": source.options.model_copy(update={"max_report_bytes": limit})}
    )


def test_all_views_use_the_same_facts_and_meaningful_type_columns():
    source = report(complete=False, state="not_evaluable")
    text = source.to_text()
    full = ParsedHTML(source.to_html())
    notebook = ParsedHTML(source._repr_html_())
    assert full.text == notebook.text
    for fact in (
        "not_evaluable",
        "output_schema",
        "partial",
        "exact; no tolerance",
        "Captured values differ",
        source.next_action,
        "at least 2",
        "lower_bound",
        "unknown",
        "approximately 10",
        "estimate",
        '"café 雪"',
        "large_string",
        "Native type",
        "Physical type",
        "unchanged_in_original_comparison",
        "until_caller_deletes",
        "caller_managed_local_storage_no_encryption",
        source.contract_sha256,
        source.spec_sha256,
    ):
        assert fact in text
        assert fact in full.text
    assert "Added rows (left relative to right) | unknown | unknown | rows" in text
    assert "Added rows (left relative to right) | 0" not in text
    assert (
        text.index("Verdict:")
        < text.index("Reasons")
        < text.index("Next action")
        < text.index("Example 1")
        < text.index("Policies")
    )
    assert text.index("Next action") < text.index("Example 1")
    assert "Display complete: false" in text
    assert "Difference records need not be distinct rows" in text
    assert 'scope="col"' in source.to_html()
    assert 'scope="row"' in source.to_html()


@pytest.mark.parametrize(
    "state,complete",
    [
        ("equivalent", True),
        ("different", True),
        ("not_evaluable", True),
        ("not_evaluable", False),
    ],
)
@pytest.mark.parametrize("renderer", RENDERERS)
def test_verdict_does_not_depend_on_complete_alone(state, complete, renderer):
    source = report(state=state, complete=complete)
    rendered = renderer(source)
    assert state in rendered
    assert ("complete" if complete else "partial") in rendered
    assert rendered == renderer(source)
    if state == "equivalent":
        assert "No recorded reasons" in rendered
        assert "Example 1" not in rendered
    elif state == "not_evaluable" and complete:
        assert "equivalent" not in rendered


@pytest.mark.parametrize("reference", ["expected", "peer"])
@pytest.mark.parametrize("renderer", RENDERERS)
def test_expected_and_peer_sides_have_accurate_labels(reference, renderer):
    rendered = renderer(report(reference=reference))
    if reference == "peer":
        assert "Peer (left)" in rendered and "Peer (right)" in rendered
        assert "Candidate (left)" not in rendered and "Expected (right)" not in rendered
        assert "Agreement between peers does not establish independent correctness" in rendered
    else:
        assert "Candidate (left)" in rendered and "Expected (right)" in rendered
        assert "its independence is not established" in rendered


@pytest.mark.parametrize("renderer", [render_comparison_html, render_comparison_notebook])
def test_arbitrary_payloads_are_only_escaped_text(renderer):
    attack = '</td></tr></table><script>alert(1)</script><img src="https://bad/x" onerror="x">'
    source = report(values=(value(attack, native=attack, physical=attack),))
    witness = source.examples[0].model_copy(
        update={
            "code": attack,
            "reason": attack,
            "column": attack,
            "key_columns": (attack,),
            "columns": (attack,),
        }
    )
    source = source.model_copy(
        update={
            "examples": (witness,),
            "reasons": (attack,),
            "next_action": attack,
            "policies": (ReportPolicy(name=attack, value=attack),),
            "evidence": source.evidence.model_copy(
                update={
                    "acceptance": "not_satisfied",
                    "unmet_requirements": (attack,),
                }
            ),
        }
    )
    rendered = renderer(source)
    parsed = ParsedHTML(rendered)
    assert attack not in rendered
    assert "&lt;script&gt;" in rendered
    assert attack in parsed.text
    assert not set(parsed.tags) & {
        "script",
        "img",
        "iframe",
        "a",
        "form",
        "object",
        "embed",
        "link",
    }
    assert not any(
        key.startswith("on") or key in {"src", "href", "srcdoc"} for key, _ in parsed.attributes
    )
    assert all("https://bad/x" not in (item or "") for _, item in parsed.attributes)
    assert not any(key in {"id", "name"} and item == attack for key, item in parsed.attributes)


def test_standalone_has_csp_and_notebook_is_an_inert_fragment():
    source = report()
    full = source.to_html()
    assert "default-src 'none'" in full
    assert "base-uri 'none'" in full
    assert "form-action 'none'" in full
    assert full.startswith('<!doctype html><html lang="en">')
    notebook = source._repr_html_()
    assert not set(ParsedHTML(notebook).tags) & {"html", "head", "body", "meta", "script"}
    assert "<details>" in notebook
    assert "<summary>Example 1" in notebook
    assert len(notebook.encode("utf-8")) < len(full.encode("utf-8")) + 400


@pytest.mark.parametrize("renderer", RENDERERS)
def test_terminal_and_unicode_controls_are_visible_in_every_arbitrary_field(renderer):
    attack = "line\nnext\r\t\x1b[31m\x00\x08\x0c\x7f\x9b\u202e\u2066\u2028\u2029 café 雪"
    source = report(values=(value(attack, native=attack, physical=attack),))
    source = source.model_copy(
        update={
            "reasons": (attack,),
            "next_action": attack,
            "policies": (ReportPolicy(name=attack, value=attack),),
        }
    )
    rendered = renderer(source)
    assert "café 雪" in rendered
    assert "line\\nnext\\r\\t\\u001b[31m\\u0000\\b\\f\\u007f\\u009b" in rendered
    assert "\\u202e\\u2066\\u2028\\u2029" in rendered
    assert not any(
        character in rendered
        for character in "\r\t\x1b\x00\x08\x0c\x7f\x9b\u202e\u2066\u2028\u2029"
    )
    assert "line\nnext" not in rendered


@pytest.mark.parametrize("renderer", RENDERERS)
def test_redacted_and_omitted_values_never_render_raw_scalar_fields(renderer):
    source = report(values=(value(disclosure="redacted"), value(disclosure="omitted")))
    witness = source.examples[0].model_copy(
        update={
            "key": (value(disclosure="redacted"),),
            "reference": (value(disclosure="omitted"),),
        }
    )
    source = source.model_copy(
        update={
            "examples": (witness,),
            "options": source.options.model_copy(update={"include_values": False}),
            "evidence": source.evidence.model_copy(update={"values_withheld": True}),
        }
    )
    rendered = renderer(source)
    assert "[redacted]" in rendered
    assert "[omitted]" in rendered
    assert "café" not in rendered
    visible = value("safe rendered representation").model_copy(
        update={
            "value": ComparisonValue(kind="string", value="SECRET_RAW_VALUE"),
        }
    )
    rendered = renderer(report(values=(visible,)))
    assert "safe rendered representation" in rendered
    assert "SECRET_RAW_VALUE" not in rendered


@pytest.mark.parametrize("renderer", RENDERERS)
def test_render_byte_limit_fails_explicitly_without_returning_a_truncation(renderer):
    source = report()
    with pytest.raises(ResourceLimitError, match="max_report_bytes"):
        renderer(with_budget(source, 1))
    limit = len(renderer(source).encode("utf-8"))
    limit -= len(str(source.options.max_report_bytes)) - len(str(limit))
    exact = with_budget(source, limit)
    assert len(renderer(exact).encode("utf-8")) == limit
    with pytest.raises(ResourceLimitError, match="max_report_bytes"):
        renderer(with_budget(source, limit - 1))


@pytest.mark.parametrize("renderer", RENDERERS)
def test_budget_counts_utf8_bytes_rather_than_characters(renderer):
    source = report(values=(value("雪" * 1000),))
    generous = renderer(source)
    candidate = with_budget(source, len(generous))
    with pytest.raises(ResourceLimitError, match="max_report_bytes"):
        renderer(candidate)


def test_pure_methods_do_not_open_files_or_import_optional_notebook_dependencies(monkeypatch):
    source = report()
    # Load renderer modules before disabling all future imports and filesystem reads.
    source.to_text()
    source.to_html()
    source._repr_html_()
    original_import = builtins.__import__

    def no_optional(name, *args, **kwargs):
        if name.split(".")[0] in {"IPython", "ipywidgets", "pandas", "polars", "pyarrow", "numpy"}:
            raise AssertionError(f"optional import attempted: {name}")
        return original_import(name, *args, **kwargs)

    def no_io(*args, **kwargs):
        raise AssertionError("renderer attempted filesystem IO")

    monkeypatch.setattr(builtins, "__import__", no_optional)
    monkeypatch.setattr(builtins, "open", no_io)
    monkeypatch.setattr(Path, "open", no_io)
    for renderer in (source.to_text, source.to_html, source._repr_html_):
        assert "EquiFrame comparison" in renderer()


def test_unknown_types_and_unmapped_columns_are_explicit():
    source = report(values=(value(native=None, physical=None), value(native=None, physical=None)))
    rendered = source.to_text()
    assert "Field 1 (column unavailable)" in rendered
    assert "Field 2 (column unavailable)" in rendered
    assert re.search(r"string \| unavailable \| unavailable", rendered)
    assert "account" in rendered
    assert "position (zero-based): 0" in rendered


@pytest.mark.parametrize(
    "scalar,representation",
    [
        (ComparisonValue(kind="null"), "null"),
        (ComparisonValue(kind="nan"), "NaN"),
        (ComparisonValue(kind="infinity", value="negative"), "-Infinity"),
        (ComparisonValue(kind="boolean", value="false"), "false"),
        (ComparisonValue(kind="string", value=""), '""'),
        (ComparisonValue(kind="integer", value="0"), "0"),
        (ComparisonValue(kind="integer", value="9007199254740993"), "9007199254740993"),
        (ComparisonValue(kind="decimal", value="-0.00"), "-0.00"),
        (ComparisonValue(kind="decimal", value="999999999999999.0100"), "999999999999999.0100"),
        (ComparisonValue(kind="float", value="-0.0"), "-0.0"),
        (ComparisonValue(kind="date", value="12345", unit="day"), "12345 day"),
        (
            ComparisonValue(
                kind="timestamp", value="1234567890123456789", unit="ns", timezone="UTC"
            ),
            "1234567890123456789 ns UTC",
        ),
    ],
)
@pytest.mark.parametrize("renderer", RENDERERS)
def test_exact_scalar_representations_are_never_normalized(scalar, representation, renderer):
    item = ReportValue(
        disclosure="visible",
        kind=scalar.kind,
        representation=representation,
        native_type="original native type",
        physical_type="original physical type",
        value=scalar,
    )
    source = report(values=(item,))
    output = renderer(source)
    if renderer is render_comparison_text:
        assert f"{representation} | visible | {scalar.kind}" in output
    else:
        cells = ParsedHTML(output).text
        assert any(
            cells[offset : offset + 3] == [representation, "visible", scalar.kind]
            for offset in range(len(cells) - 2)
        )
    assert "original native type" in output
    assert "original physical type" in output


@pytest.mark.parametrize("renderer", RENDERERS)
def test_empty_evidence_and_missing_positions_do_not_fabricate_examples(renderer):
    source = report()
    witness = source.examples[0].model_copy(
        update={
            "position": None,
            "other_position": None,
            "key": (),
            "candidate": (),
            "reference": (),
            "candidate_count": 3,
            "reference_count": 1,
        }
    )
    output = renderer(source.model_copy(update={"examples": (witness,)}))
    assert "Example 1: values and types" not in output
    if renderer is render_comparison_text:
        assert "Candidate (left) position (zero-based): unavailable" in output
        assert "Expected (right) position (zero-based): unavailable" in output
        assert "Candidate (left) occurrences: 3" in output
        assert "Expected (right) occurrences: 1" in output
    else:
        cells = ParsedHTML(output).text
        position = cells.index("Candidate (left) position (zero-based)")
        assert cells[position + 1] == "unavailable"
        occurrence = cells.index("Candidate (left) occurrences")
        assert cells[occurrence + 1] == "3"


def test_reason_and_unmet_requirement_limits_remain_visible():
    source = report(complete=False, state="not_evaluable")
    source = source.model_copy(
        update={
            "evidence": source.evidence.model_copy(
                update={
                    "required_exhaustive": True,
                    "acceptance": "not_satisfied",
                    "unmet_requirements": ("incomplete evaluation", "example budget reached"),
                }
            ),
            "options": source.options.model_copy(update={"require_exhaustive": True}),
        }
    )
    for renderer in RENDERERS:
        output = renderer(source)
        assert "not_satisfied" in output
        assert "incomplete evaluation" in output
        assert "example budget reached" in output
        assert "not_evaluable" in output


def test_rendering_never_modifies_the_report_on_success_or_failure():
    source = report()
    original = source.model_dump()
    for renderer in RENDERERS:
        renderer(source)
        with pytest.raises(ResourceLimitError):
            renderer(with_budget(source, 1))
        assert source.model_dump() == original


@pytest.mark.parametrize("renderer", RENDERERS)
def test_lone_surrogates_are_visible_escapes_not_invalid_utf8(renderer):
    source = report(values=(value("before\ud800after"),))
    output = renderer(source)
    assert "before\\ud800after" in output
    output.encode("utf-8")


@pytest.mark.parametrize("renderer", RENDERERS)
def test_canonical_row_count_labels_follow_peer_roles(renderer):
    source = report(reference="peer")
    source = source.model_copy(
        update={
            "counts": tuple(
                count.model_copy(update={"value": 2, "precision": "exact"})
                if count.name == "candidate_excess_occurrences"
                else count
                for count in source.counts
            )
        }
    )
    output = renderer(source)
    assert "Peer (left) rows" in output and "Peer (right) rows" in output
    assert "Peer (left) excess occurrences" in output
    assert "candidate_rows" not in output


@pytest.mark.parametrize("category", ["contract", "schema"])
def test_contract_default_counts_do_not_claim_zero_row_occurrences(category):
    source = report()
    witness = source.examples[0].model_copy(
        update={
            "category": category,
            "candidate_count": None,
            "reference_count": None,
        }
    )
    text = source.model_copy(update={"examples": (witness,)}).to_text()
    assert "Candidate (left) occurrences: unavailable" in text
    assert "Expected (right) occurrences: unavailable" in text
