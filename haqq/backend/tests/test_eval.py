"""Regression gate on the labelled evaluation set (eval/clause_gold.json)."""

from eval.run_eval import evaluate


def test_contract_engine_meets_quality_bar():
    s = evaluate()["summary"]
    assert s["n"] >= 19
    assert s["category_accuracy"] >= 0.9
    assert s["notice_period_accuracy"] == 1.0
    assert s["time_bar_accuracy"] == 1.0
    assert s["exclusion_accuracy"] >= 0.9
    assert s["payment_period_accuracy"] == 1.0
