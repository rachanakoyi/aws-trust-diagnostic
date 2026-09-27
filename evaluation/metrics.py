"""Evaluation metrics for AWS Anomaly Detection and Diagnostic Classification.

Calculates Precision, Recall, F1-Score, Confusion Matrix, False Alarm Rate,
Missed Anomaly Rate, and Ingestion/Inference Latency.
"""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix


def compute_binary_metrics(
    y_true: List[int],
    y_pred: List[int],
    latencies_ms: Optional[List[float]] = None
) -> Dict[str, Any]:
    """Compute binary anomaly detection performance metrics.
    
    y_true: 1 for anomaly (fault or event), 0 for normal
    y_pred: 1 for anomaly, 0 for normal
    """
    y_t = np.array(y_true)
    y_p = np.array(y_pred)

    if len(y_t) == 0:
        return {}

    cm = confusion_matrix(y_t, y_p, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_t, y_p, average="binary", zero_division=0
    )

    # False Alarm Rate: FP / (FP + TN)
    far = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    # Missed Anomaly Rate: FN / (TP + FN)
    mar = float(fn / (tp + fn)) if (tp + fn) > 0 else 0.0

    avg_latency = float(np.mean(latencies_ms)) if latencies_ms else 0.0

    return {
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1_score": round(float(f1), 4),
        "false_alarm_rate": round(far, 4),
        "missed_anomaly_rate": round(mar, 4),
        "accuracy": round(float((tp + tn) / len(y_t)), 4),
        "confusion_matrix": cm.tolist(),
        "avg_latency_ms": round(avg_latency, 2),
        "total_samples": len(y_t)
    }


def compute_multiclass_metrics(
    y_true_labels: List[str],
    y_pred_labels: List[str],
    classes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Compute 3-way fault discrimination metrics.
    
    Classes: ['NORMAL', 'PROBABLE_SENSOR_FAULT', 'PROBABLE_GENUINE_EVENT', 'UNCERTAIN']
    """
    labels = classes or ["NORMAL", "PROBABLE_SENSOR_FAULT", "PROBABLE_GENUINE_EVENT", "UNCERTAIN"]
    cm = confusion_matrix(y_true_labels, y_pred_labels, labels=labels)

    prec, rec, f1, support = precision_recall_fscore_support(
        y_true_labels, y_pred_labels, labels=labels, zero_division=0
    )

    per_class = {}
    for i, c in enumerate(labels):
        per_class[c] = {
            "precision": round(float(prec[i]), 3),
            "recall": round(float(rec[i]), 3),
            "f1_score": round(float(f1[i]), 3),
            "support": int(support[i])
        }

    overall_acc = float(np.mean(np.array(y_true_labels) == np.array(y_pred_labels)))

    return {
        "overall_accuracy": round(overall_acc, 4),
        "per_class": per_class,
        "labels": labels,
        "confusion_matrix": cm.tolist(),
        "total_samples": len(y_true_labels)
    }
