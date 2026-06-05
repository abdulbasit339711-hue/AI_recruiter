import os
import sys
import json
from datetime import datetime, timezone

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Candidate, Job

def generate_report():
    print("Generating Executive Recruitment Report...")
    db = SessionLocal()
    try:
        jobs = db.query(Job).all()
        if not jobs:
            print("No jobs found in the database. Please run test_scoring.py first.")
            return

        report_md = []
        report_md.append("# 💼 EXECUTIVE RECRUITMENT REPORT")
        report_md.append(f"**Generated At:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        report_md.append("\n---\n")

        for job in jobs:
            report_md.append(f"## 📋 Job Profile: {job.title} ({job.department})")
            report_md.append(f"**Status:** {job.status}")
            report_md.append("\n**Target Job Description:**")
            report_md.append(f"> {job.job_description}\n")

            candidates = db.query(Candidate).filter(Candidate.job_id == job.id).order_by(Candidate.total_score.desc()).all()
            if not candidates:
                report_md.append("_No candidates evaluated yet for this job._\n")
                continue

            # Core Stats
            total = len(candidates)
            passed = sum(1 for c in candidates if c.status == "Processed")
            failed = total - passed
            avg_score = sum(c.total_score for c in candidates if c.status == "Processed") / max(1, passed)

            report_md.append("### 📊 Metrics Summary")
            report_md.append(f"- **Total Applicants:** {total}")
            report_md.append(f"- **Passed Screening:** {passed}")
            report_md.append(f"- **Failed Screening:** {failed}")
            report_md.append(f"- **Average Processed Score:** {avg_score:.1f}/100\n")

            # Rankings Table
            report_md.append("### 🏆 Candidate Rankings")
            report_md.append("| Rank | Candidate Name | Email | Total Score | Tier 1 (Rules) | Tier 2 (Semantic) | Tier 3 (LLM) | Status |")
            report_md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            
            for idx, cand in enumerate(candidates, 1):
                name = cand.filename.replace("_Resume.pdf", "").replace("_", " ")
                email = cand.email or "N/A"
                report_md.append(
                    f"| {idx} | {name} | `{email}` | **{cand.total_score:.1f}** | {cand.tier1:.1f} | {cand.tier2:.1f} | {cand.tier3:.1f} | {cand.status} |"
                )
            report_md.append("\n")

            # Deep-dive summaries
            report_md.append("### 🔍 Top Candidates Qualitative Analysis")
            for cand in candidates:
                if cand.status != "Processed":
                    continue
                name = cand.filename.replace("_Resume.pdf", "").replace("_", " ")
                report_md.append(f"#### 👤 {name} (Total Score: {cand.total_score:.1f}/100)")
                report_md.append(f"- **Email:** `{cand.email or 'N/A'}`")
                report_md.append(f"- **Tier Breakdown:** Profile Rules: {cand.tier1}/30 | Semantic: {cand.tier2}/40 | LLM Evaluation: {cand.tier3}/30")
                if cand.summary:
                    report_md.append(f"- **Executive Summary:** {cand.summary}")
                else:
                    report_md.append("- **Executive Summary:** Not evaluated by LLM.")
                
                if cand.evidence:
                    try:
                        evidences = json.loads(cand.evidence)
                        report_md.append("- **Key Evidence:**")
                        for ev in evidences:
                            report_md.append(f"  - {ev}")
                    except Exception:
                        report_md.append(f"- **Evidence:** {cand.evidence}")
                report_md.append("")
            
            report_md.append("\n---\n")

        # Save to file
        report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recruitment_report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_md))

        print(f"Successfully generated recruitment report: {report_path}")

    finally:
        db.close()

if __name__ == "__main__":
    generate_report()
