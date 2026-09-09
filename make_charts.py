import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")


def make_charts():
    merged = pd.read_csv(os.path.join(OUT_DIR, "weekly_summary.csv"))

    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(merged.week, merged.participation_rate_baseline * 100, marker="o",
            label="Baseline (static feedback)", color="#c0392b")
    ax.plot(merged.week, merged.participation_rate_prototype * 100, marker="o",
            label="Prototype (plain-language, adaptive)", color="#1f6f43")
    ax.axhline(75, color="gray", linestyle="--", linewidth=1, label="Target (75%)")
    ax.set_xlabel("Week")
    ax.set_ylabel("Participation rate (%)")
    ax.set_title("Sustained participation over 8 weeks")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "chart_participation.png"), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(merged.week, merged.comprehension_rate_baseline * 100, marker="o",
            label="Baseline (numbers only)", color="#c0392b")
    ax.plot(merged.week, merged.comprehension_rate_prototype * 100, marker="o",
            label="Prototype (plain-language)", color="#1f6f43")
    ax.axhline(80, color="gray", linestyle="--", linewidth=1, label="Target (80%)")
    ax.set_xlabel("Week")
    ax.set_ylabel("Comprehension check correct (%)")
    ax.set_title("Comprehension of progress feedback over 8 weeks")
    ax.set_ylim(0, 105)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "chart_comprehension.png"), dpi=150)
    plt.close(fig)

    print("Charts written to", OUT_DIR)


if __name__ == "__main__":
    make_charts()
