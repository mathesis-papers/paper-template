"""Shared request links for reviewed paper mappings; never proof receipts."""
import re


def result_requests(mapping):
    requests = {}
    for result_id, row in mapping.get("results", {}).items():
        link = row.get("formalization_request")
        if link is None:
            continue
        if not isinstance(link, dict) or set(link) != {"label", "url"}:
            raise ValueError(f"#{result_id}: formalization_request needs label and url")
        url, label = link["url"], link["label"]
        if not isinstance(url, str) or not re.fullmatch(
            r"https://github.com/the-omega-institute/trureturing-requests/issues/[1-9][0-9]{0,19}", url
        ):
            raise ValueError(f"#{result_id}: invalid formalization request URL")
        if not isinstance(label, str) or not label.strip() or label != label.strip() or len(label) > 300 or "\n" in label or "\r" in label:
            raise ValueError(f"#{result_id}: formalization request needs a plain readable label")
        if row.get("comparison_verdict") == "same":
            raise ValueError(f"#{result_id}: an exactly covered result cannot request another proof")
        requests.setdefault(url, set()).add(label)
    return [{"url": url, "label": "; ".join(sorted(labels))}
            for url, labels in sorted(requests.items(), key=lambda item: int(item[0].rsplit("/", 1)[1]))]
