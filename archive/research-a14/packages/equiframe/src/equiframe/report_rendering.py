"""Pure, bounded renderers for already disclosed comparison facts.

No renderer reads an artifact, imports a notebook framework or executes user HTML.
All three views consume the same sections, including evidence limitations. The
standalone document adds a restrictive CSP; notebook fragments contain only
escaped text and locally scoped, static markup/styles.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from html import escape
from unicodedata import category

from equiframe.errors import ResourceLimitError
from equiframe.report_types import ComparisonReport, ReportCount, ReportValue, ReportWitness


@dataclass(frozen=True)
class _Section:
    title: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    compact: bool = False


@dataclass
class _Output:
    limit: int
    parts: list[str] = field(default_factory=list)
    size: int = 0

    def write(self, fragment: str) -> None:
        self.size += len(fragment.encode("utf-8"))
        if self.size > self.limit:
            raise ResourceLimitError("comparison report exceeds max_report_bytes")
        self.parts.append(fragment)

    def finish(self) -> str:
        return "".join(self.parts)


def _safe_text(value: str) -> str:
    """Make terminal controls, bidi controls and line injection visible as escapes."""
    result: list[str] = []
    short = {"\n": "\\n", "\r": "\\r", "\t": "\\t", "\b": "\\b", "\f": "\\f"}
    for char in value:
        if char in short:
            result.append(short[char])
        elif category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"}:
            number = ord(char)
            result.append(f"\\u{number:04x}" if number <= 0xFFFF else f"\\U{number:08x}")
        else:
            result.append(char)
    return "".join(result)


def _html_text(value: str) -> str:
    return escape(_safe_text(value), quote=True)


def _boolean(value: bool) -> str:
    return "true" if value else "false"


def _roles(report: ComparisonReport) -> tuple[str, str]:
    if report.reference == "expected":
        return "Candidate (left)", "Expected (right)"
    return "Peer (left)", "Peer (right)"


def _count_label(name: str, report: ComparisonReport) -> str:
    candidate, reference = _roles(report)
    labels = {
        "candidate_rows": f"{candidate} rows",
        "reference_rows": f"{reference} rows",
        "candidate_excess_occurrences": f"{candidate} excess occurrences",
        "reference_excess_occurrences": f"{reference} excess occurrences",
        "matched_rows": "Matched rows",
        "difference_records": "Difference records",
        "contract_violations": "Contract violation records",
        "added_rows": "Added rows (left relative to right)",
        "removed_rows": "Removed rows (left relative to right)",
        "modified_rows": "Modified aligned rows",
    }
    return labels.get(name, name)


def _count_value(count: ReportCount) -> str:
    if count.precision == "unknown":
        return "unknown"
    if count.precision == "lower_bound":
        return f"at least {count.value}"
    if count.precision == "estimate":
        return f"approximately {count.value}"
    return str(count.value)


def _column_labels(witness: ReportWitness, size: int, *, key: bool = False) -> tuple[str, ...]:
    columns = witness.key_columns if key else witness.columns
    if not key and witness.column is not None and size == 1:
        return (witness.column,)
    if len(columns) == size:
        return columns
    return tuple(f"Field {index + 1} (column unavailable)" for index in range(size))


def _value_row(side: str, column: str, value: ReportValue) -> tuple[str, ...]:
    return (
        side,
        column,
        value.representation,
        value.disclosure,
        value.kind,
        value.native_type if value.native_type is not None else "unavailable",
        value.physical_type if value.physical_type is not None else "unavailable",
    )


def _witness_sections(report: ComparisonReport) -> Iterator[_Section]:
    candidate, reference = _roles(report)
    for number, witness in enumerate(report.examples, 1):
        yield _Section(
            f"Example {number}: location and reason",
            ("Fact", "Value"),
            (
                ("Category", witness.category),
                ("Code", witness.code),
                ("Reason", witness.reason),
                (
                    f"{candidate} position (zero-based)",
                    str(witness.position) if witness.position is not None else "unavailable",
                ),
                (
                    f"{reference} position (zero-based)",
                    str(witness.other_position)
                    if witness.other_position is not None
                    else "unavailable",
                ),
                ("Column", witness.column if witness.column is not None else "not specified"),
                (
                    f"{candidate} occurrences",
                    str(witness.candidate_count)
                    if witness.candidate_count is not None
                    else "unavailable",
                ),
                (
                    f"{reference} occurrences",
                    str(witness.reference_count)
                    if witness.reference_count is not None
                    else "unavailable",
                ),
            ),
            compact=True,
        )
        rows: list[tuple[str, ...]] = []
        for side, values, key in (
            ("Key", witness.key, True),
            (candidate, witness.candidate, False),
            (reference, witness.reference, False),
        ):
            labels = _column_labels(witness, len(values), key=key)
            rows.extend(
                _value_row(side, column, value)
                for column, value in zip(labels, values, strict=True)
            )
        if rows:
            yield _Section(
                f"Example {number}: values and types",
                ("Side", "Column", "Value", "Disclosure", "Kind", "Native type", "Physical type"),
                tuple(rows),
                compact=True,
            )


def _sections(report: ComparisonReport) -> Iterator[_Section]:
    yield _Section(
        "Verdict and coverage",
        ("Fact", "Value"),
        (
            ("Verdict", report.state),
            ("Evaluation complete", _boolean(report.complete)),
            ("Scope", report.scope),
            ("Reference role", report.reference),
            (
                "Interpretation",
                (
                    "Comparison against the declared expected output; "
                    "its independence is not established"
                )
                if report.reference == "expected"
                else "Agreement between peers does not establish independent correctness",
            ),
            ("Strategy", report.strategy),
            ("Coverage", report.coverage),
        ),
    )
    yield _Section(
        "Reasons",
        ("Reason",),
        tuple((reason,) for reason in report.reasons) or (("No recorded reasons",),),
    )
    yield _Section("Next action", ("Action",), ((report.next_action,),))
    yield _Section(
        "Counts",
        ("Measure", "Value", "Precision", "Unit"),
        tuple(
            (_count_label(count.name, report), _count_value(count), count.precision, count.unit)
            for count in report.counts
        )
        or (("Counts", "unknown", "unknown", "not specified"),),
    )
    yield _Section(
        "Displayed examples",
        ("Fact", "Value"),
        (
            ("Included examples", str(report.evidence.included_examples)),
            ("Available difference records", str(report.evidence.available_records)),
            ("Display complete", _boolean(report.evidence.display_complete)),
            ("Counting scope", "Difference records need not be distinct rows"),
        ),
    )
    yield from _witness_sections(report)
    yield _Section(
        "Policies",
        ("Policy", "Value"),
        tuple((policy.name, policy.value) for policy in report.policies)
        or (("Policy entries", "none recorded"),),
    )
    evidence = report.evidence
    yield _Section(
        "Evidence and limitations",
        ("Fact", "Value"),
        (
            ("Evidence schema version", evidence.schema_version),
            ("Evidence mode", evidence.mode),
            ("Inspection", evidence.inspection),
            ("Evaluation complete", _boolean(evidence.evaluation_complete)),
            ("Counts final", _boolean(evidence.counts_final)),
            ("Values withheld", _boolean(evidence.values_withheld)),
            ("Metadata withheld", _boolean(evidence.metadata_withheld)),
            ("Original evidence retention", evidence.raw_retention),
            ("Report retention", evidence.report_retention),
            ("Access", evidence.access),
            ("Exhaustive evidence required", _boolean(evidence.required_exhaustive)),
            ("Evidence requirements", evidence.acceptance),
            ("Reproduction", evidence.reproduction),
            ("Reproduction scope", evidence.reproduction_scope),
        ),
        compact=True,
    )
    if evidence.unmet_requirements:
        yield _Section(
            "Unmet evidence requirements",
            ("Requirement",),
            tuple((requirement,) for requirement in evidence.unmet_requirements),
            compact=True,
        )
    options = report.options
    yield _Section(
        "Report disclosure and limits",
        ("Setting", "Value"),
        (
            ("Mode", options.mode),
            ("Include values", _boolean(options.include_values)),
            ("Include metadata", _boolean(options.include_metadata)),
            ("Redacted columns", str(options.redacted_column_count)),
            ("Maximum examples", str(options.max_examples)),
            ("Maximum value characters", str(options.max_value_chars)),
            ("Maximum report bytes", str(options.max_report_bytes)),
            ("Require exhaustive evidence", _boolean(options.require_exhaustive)),
        ),
        compact=True,
    )
    yield _Section(
        "Identity",
        ("Fact", "Value"),
        (
            ("Report schema version", report.schema_version),
            ("Contract SHA-256", report.contract_sha256),
            ("Comparison specification SHA-256", report.spec_sha256),
        ),
        compact=True,
    )


_STYLE = (
    ".equiframe-report{font:14px system-ui,sans-serif;color:#172b3a;"
    "background:#fff;max-width:1100px;padding:1rem;overflow-wrap:anywhere}"
    ".equiframe-report h1{font-size:1.5rem}.equiframe-report h2{font-size:1.1rem}"
    ".equiframe-report table{width:100%;border-collapse:collapse;margin:.6rem 0 1rem}"
    ".equiframe-report .equiframe-facts{table-layout:fixed}"
    ".equiframe-report .equiframe-facts th:first-child{width:25%}"
    ".equiframe-report th,.equiframe-report td{padding:.4rem;border:1px solid #ccd5df;"
    "text-align:left;vertical-align:top;white-space:pre-wrap}"
    ".equiframe-report thead{background:#f0f4f7}.equiframe-report summary{"
    "cursor:pointer;font-weight:bold;margin:.6rem 0}"
    "@media print{.equiframe-report{max-width:none}}"
)


def _write_html(output: _Output, report: ComparisonReport, *, compact: bool) -> None:
    output.write("<style>" + _STYLE + '</style><section class="equiframe-report">')
    output.write("<h1>EquiFrame comparison</h1>")
    for section in _sections(report):
        collapsed = compact and section.compact
        if collapsed:
            output.write("<details><summary>" + _html_text(section.title) + "</summary>")
        else:
            output.write("<section><h2>" + _html_text(section.title) + "</h2>")
        output.write(
            '<table class="equiframe-facts"><thead><tr>'
            if len(section.headers) == 2
            else "<table><thead><tr>"
        )
        for header in section.headers:
            output.write('<th scope="col">' + _html_text(header) + "</th>")
        output.write("</tr></thead><tbody>")
        for row in section.rows:
            output.write("<tr>")
            for index, cell in enumerate(row):
                if index == 0 and len(section.headers) == 2:
                    output.write('<th scope="row">' + _html_text(cell) + "</th>")
                else:
                    output.write("<td>" + _html_text(cell) + "</td>")
            output.write("</tr>")
        output.write("</tbody></table>" + ("</details>" if collapsed else "</section>"))
    output.write("</section>")


def render_comparison_text(report: ComparisonReport) -> str:
    """Render all disclosed facts as plain text, escaping terminal control characters."""
    report = ComparisonReport.model_validate(report)
    output = _Output(report.options.max_report_bytes)
    output.write("EquiFrame comparison\n")
    for section in _sections(report):
        output.write("\n" + _safe_text(section.title) + "\n")
        if len(section.headers) > 2:
            output.write(" | ".join(_safe_text(header) for header in section.headers) + "\n")
        for row in section.rows:
            separator = ": " if len(row) == 2 else " | "
            output.write(separator.join(_safe_text(cell) for cell in row) + "\n")
    return output.finish()


def render_comparison_html(report: ComparisonReport) -> str:
    """Render a standalone inert HTML document, or raise when its UTF-8 budget is exceeded."""
    report = ComparisonReport.model_validate(report)
    output = _Output(report.options.max_report_bytes)
    output.write(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>EquiFrame comparison</title></head><body>"
    )
    _write_html(output, report, compact=False)
    output.write("</body></html>")
    return output.finish()


def render_comparison_notebook(report: ComparisonReport) -> str:
    """Render a compact inert fragment without IO, JavaScript or optional dependencies."""
    report = ComparisonReport.model_validate(report)
    output = _Output(report.options.max_report_bytes)
    _write_html(output, report, compact=True)
    return output.finish()
