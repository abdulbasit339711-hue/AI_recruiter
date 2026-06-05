import os
import smtplib
import sys
import json
import pandas as pd
import streamlit as st
from datetime import datetime, timezone
from email.message import EmailMessage
from dotenv import load_dotenv
import time
import concurrent.futures
# sys.path will be adjusted below before any app imports
# Add the project root to sys.path BEFORE importing any app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Load environment variables from project root .env (three levels up)
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')))

# Retrieve SMTP credentials from .env
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

from app.database import SessionLocal, config, Base, engine
from app.models import Candidate, Job
from app.scoring.engine import evaluate_candidate_pipeline
from app.intake.upload import validate_and_extract, IngestionError
from app.queue.worker import enqueue_candidate, start_worker
from app.core import status as CandStatus

start_worker()

# Initialize ThreadPoolExecutor for scoring tasks (once per session)
if 'scoring_executor' not in st.session_state:
    st.session_state.scoring_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


# Streamlit Page Config
st.set_page_config(
    page_title="AI Recruiter Leaderboard",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Mode / Premium Custom Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main {
        background: linear-gradient(135deg, #0e1117 0%, #161a24 100%);
    }
    
    .title-banner {
        background: linear-gradient(90deg, #6366f1 0%, #a855f7 100%);
        padding: 2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px -5px rgba(99, 102, 241, 0.3);
    }
    
    .title-banner h1 {
        font-weight: 800;
        font-size: 2.5rem;
        margin: 0;
    }
    .title-banner p {
        font-weight: 300;
        opacity: 0.9;
        margin: 0.5rem 0 0 0;
    }
    
    .metric-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        backdrop-filter: blur(10px);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow: 0 12px 20px -8px rgba(99, 102, 241, 0.2);
    }
    
    .metric-val {
        font-size: 2.2rem;
        font-weight: 800;
        color: #6366f1;
        margin-bottom: 0.2rem;
    }
    
    .metric-label {
        font-size: 0.9rem;
        font-weight: 400;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .detail-container {
        background: rgba(255, 255, 255, 0.02);
        border-left: 4px solid #6366f1;
        padding: 1.5rem;
        border-radius: 0 12px 12px 0;
        margin-top: 1rem;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Re-score all candidates when JD changes for a job
def rescore_all_for_job(job_id: int):
    db = SessionLocal()
    try:
        candidates = db.query(Candidate).filter(Candidate.job_id == job_id).all()
        if not candidates:
            st.info("No candidates assigned to this job to re-score.")
            return
            
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, cand in enumerate(candidates):
            status_text.text(f"Re-scoring {cand.filename} ({idx+1}/{len(candidates)})...")
            try:
                evaluate_candidate_pipeline(cand.id, db)
            except Exception as e:
                st.error(f"Failed to score {cand.filename}: {e}")
            progress_bar.progress((idx + 1) / len(candidates))
            
        progress_bar.empty()
        status_text.empty()
        st.success("Successfully re-scored all candidates against the updated Job Description!")
    finally:
        db.close()

def main():
    # Make sure DB schema is created on run
    Base.metadata.create_all(bind=engine)
    
    # 1. Header Banner
    st.markdown("""
    <div class="title-banner">
        <h1>AI Recruiter Leaderboard</h1>
        <p>Unified Candidate Parser & Multi-Job Semantic Scoring System</p>
    </div>
    """, unsafe_allow_html=True)

    db = SessionLocal()
    
    try:
        # Check archived toggle in sidebar
        show_archived = st.sidebar.checkbox("Show Archived Jobs", value=False)
        
        # Load Jobs list
        jobs_query = db.query(Job)
        if not show_archived:
            jobs_query = jobs_query.filter(Job.status == "Active")
        all_jobs = jobs_query.all()
        
        # 2. Sidebar Portal Ingest & Job Manager
        with st.sidebar:
            st.header("🎯 Job Operations")
            
            # --- CRITICAL: Job Creation & Manager Form ---
            with st.expander("🛠️ Job Management Panel", expanded=False):
                job_action = st.radio("Choose Action:", ["Create Job", "Edit Job", "Archive Job"])
                
                if job_action == "Create Job":
                    create_title = st.text_input("Job Title:")
                    create_dept = st.text_input("Department:")
                    create_jd = st.text_area("Job Description (JD):", height=150)
                    create_prompt = st.text_area(
                        "Custom LLM Prompt (Optional):", 
                        placeholder="Leave blank for standard expert recruiter prompt...",
                        height=100
                    )
                    
                    if st.button("➕ Create Job Profile", type="primary", use_container_width=True):
                        if create_title and create_dept and create_jd:
                            new_job = Job(
                                title=create_title,
                                department=create_dept,
                                job_description=create_jd,
                                llm_prompt=create_prompt if create_prompt.strip() else None,
                                status="Active",
                                created_at=datetime.now(timezone.utc).isoformat()
                            )
                            db.add(new_job)
                            db.commit()
                            st.success(f"Created Job: {create_title}")
                            st.rerun()
                        else:
                            st.error("Please fill in Job Title, Department, and Job Description!")
                            
                elif job_action == "Edit Job":
                    if not all_jobs:
                        st.info("No jobs to edit.")
                    else:
                        edit_options = {f"{j.title} ({j.department})": j.id for j in all_jobs}
                        selected_edit = st.selectbox("Select Job to Edit:", options=list(edit_options.keys()))
                        edit_job_id = edit_options[selected_edit]
                        job_to_edit = db.query(Job).filter(Job.id == edit_job_id).first()
                        
                        if job_to_edit:
                            edit_title = st.text_input("Edit Title:", value=job_to_edit.title)
                            edit_dept = st.text_input("Edit Department:", value=job_to_edit.department)
                            edit_jd = st.text_area("Edit Job Description:", value=job_to_edit.job_description, height=150)
                            edit_prompt = st.text_area("Edit Custom LLM Prompt:", value=job_to_edit.llm_prompt or "", height=100)
                            edit_status = st.selectbox("Status:", ["Active", "Archived"], index=0 if job_to_edit.status == "Active" else 1)
                            
                            if st.button("💾 Save Changes", type="primary", use_container_width=True):
                                job_to_edit.title = edit_title
                                job_to_edit.department = edit_dept
                                job_to_edit.job_description = edit_jd
                                job_to_edit.llm_prompt = edit_prompt if edit_prompt.strip() else None
                                job_to_edit.status = edit_status
                                db.commit()
                                st.success("Job updated successfully!")
                                # If JD changed, offer candidate re-scoring
                                if st.button("🔄 Re-score assigned candidates now?"):
                                    rescore_all_for_job(job_to_edit.id)
                                st.rerun()
                                
                elif job_action == "Archive Job":
                    if not all_jobs:
                        st.info("No jobs to archive.")
                    else:
                        archive_options = {f"{j.title} ({j.department})": j.id for j in all_jobs if j.status == "Active"}
                        if not archive_options:
                            st.info("No active jobs to archive.")
                        else:
                            selected_archive = st.selectbox("Select Job to Archive:", options=list(archive_options.keys()))
                            archive_job_id = archive_options[selected_archive]
                            
                            st.warning("Archiving a job soft-deletes it. The job will be hidden from default selections, but candidate history will be fully preserved.")
                            if st.button("🗄️ Soft-Archive Job", type="primary", use_container_width=True):
                                job_to_archive = db.query(Job).filter(Job.id == archive_job_id).first()
                                if job_to_archive:
                                    job_to_archive.status = "Archived"
                                    db.commit()
                                    st.success(f"Archived Job: {job_to_archive.title}")
                                    st.rerun()
            
            st.markdown("---")
            st.header("📤 Ingest Resumes")
            
            if not all_jobs:
                st.info("Create an Active Job above before uploading resumes.")
                uploaded_files = None
            else:
                upload_job_options = {f"{j.title} ({j.department})": j.id for j in all_jobs if j.status == "Active"}
                if not upload_job_options:
                    st.info("Create or restore an Active Job to upload resumes.")
                    uploaded_files = None
                else:
                    selected_upload_job = st.selectbox("Assign uploads to Job:", options=list(upload_job_options.keys()))
                    upload_job_id = upload_job_options[selected_upload_job]
                    
                    uploaded_files = st.file_uploader(
                        "Upload Resume PDFs:",
                        type=["pdf"],
                        accept_multiple_files=True,
                        help="Limit 5MB per PDF. Rejects scanned documents."
                    )
                    
                    # Global thread pool for scoring (only once)
                    if 'scoring_executor' not in st.session_state:
                        import concurrent.futures
                        st.session_state.scoring_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
                    
                    if uploaded_files:
                        futures = []
                        for uploaded_file in uploaded_files:
                            # ---- Size guard (5 MB) ----
                            if uploaded_file.size > 5 * 1024 * 1024:
                                st.warning(f"'{uploaded_file.name}' exceeds 5 MB limit – skipping.")
                                continue
                            try:
                                file_bytes = uploaded_file.read()
                                
                                # Prevent duplicates per job
                                existing = db.query(Candidate).filter(
                                    Candidate.filename == uploaded_file.name,
                                    Candidate.job_id == upload_job_id
                                ).first()
                                if existing:
                                    st.info(f"'{uploaded_file.name}' is already assigned to this job. Skipping.")
                                    continue
                                
                                # Parse text
                                raw_text = validate_and_extract(file_bytes, uploaded_file.name)
                                
                                # Extract email (simple regex)
                                import re
                                email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", raw_text)
                                email_addr = email_match.group(0) if email_match else None
                                
                                # Save Candidate record (including extracted name if present)
                                cand = Candidate(
                                    filename=uploaded_file.name,
                                    raw_text=raw_text,
                                    email=email_addr,
                                    job_id=upload_job_id,
                                    status=CandStatus.QUEUED,
                                    created_at=datetime.now(timezone.utc).isoformat()
                                )
                                db.add(cand)
                                db.commit()
                                db.refresh(cand)
                                
                                enqueue_candidate(cand.id)
                                futures.append((uploaded_file.name, None))
                            except IngestionError as ie:
                                st.error(f"Validation failed for {uploaded_file.name}: {ie.message}")
                            except Exception as e:
                                st.error(f"System error ingesting {uploaded_file.name}: {e}")

                        # Show progress while futures complete
                        # Overall progress bar (0‑100%)
                        overall_progress = st.progress(0)
                        progress_placeholder = st.empty()
                        total = len(futures)
                        for idx, (fname, _) in enumerate(futures, start=1):
                            st.success(f"Queued for evaluation: {fname}")
                            overall_progress.progress(int(idx / total * 100))
                        st.rerun()

        # 3. Main Board Display Job Selector
        st.subheader("📋 Active Job Focus")
        if not all_jobs:
            st.info("No active Job Profiles found. Click 'Job Management Panel' in the sidebar to create your first Job!")
            return
            
        view_job_options = {f"{j.title} ({j.department}) {'[ARCHIVED]' if j.status == 'Archived' else ''}": j.id for j in all_jobs}
        selected_view_job = st.selectbox("Display Leaderboard for:", options=list(view_job_options.keys()))
        view_job_id = view_job_options[selected_view_job]
        
        active_job = db.query(Job).filter(Job.id == view_job_id).first()
        
        # Display Active Job JD / details
        with st.expander("📄 View Target Job Description Details", expanded=False):
            col_jd_left, col_jd_right = st.columns([2, 1])
            with col_jd_left:
                st.write("**Title**:", active_job.title)
                st.write("**Department**:", active_job.department)
                st.write("**Status**:", active_job.status)
                st.write("**Created At**:", active_job.created_at)
                st.text_area("Target Job Description (JD):", value=active_job.job_description, height=200, disabled=True)
            with col_jd_right:
                st.text_area("Custom LLM system prompt:", value=active_job.llm_prompt or "Default prompt active.", height=200, disabled=True)
                if st.button("🔄 Trigger Re-scoring of candidates", use_container_width=True):
                    rescore_all_for_job(active_job.id)
                    st.rerun()

        # ---- Email Notification Controls ----
        with st.sidebar.expander("📧 Email Notifications", expanded=False):
            # Only shortlisted (Processed) candidates will receive emails
            shortlisted = db.query(Candidate).filter(
                Candidate.job_id == active_job.id,
                Candidate.status.in_([CandStatus.SHORTLISTED, "Processed"]),
            ).order_by(Candidate.total_score.desc()).all()

            st.write(f"✅ Shortlisted candidates: {len(shortlisted)}")

            if shortlisted:
                max_to_email = len(shortlisted)
                if max_to_email > 1:
                    top_n = st.slider(
                        "Number of top candidates to email",
                        min_value=1,
                        max_value=max_to_email,
                        value=max_to_email,
                        key="top_n_slider",
                    )
                else:
                    top_n = 1
                if st.button("Send Shortlist Emails"):
                    for cand in shortlisted[:top_n]:
                        subject = f"Your Application for {active_job.title} – Shortlisted"
                        body = f"Dear {cand.filename.replace('_Resume.pdf', '').replace('_', ' ')},\n\n"
                        body += "We are pleased to inform you that you have been shortlisted for the next stage of our hiring process. Our recruitment team will contact you shortly with further details.\n\n"
                        body += "Best regards,\nAI Recruiter Team"
                        try:
                            if cand.email:
                                send_email(cand.email, subject, body)
                                st.success(f"Email sent to {cand.email}")
                            else:
                                st.warning(f"Candidate {cand.filename} has no email address; skipping.")
                        except Exception as e:
                            st.error(f"Failed to send email to {cand.email}: {e}")
            else:
                st.info("No shortlisted candidates to email.")

        # 4. Analytics & Overview row (for selected job)
        candidates = db.query(Candidate).filter(Candidate.job_id == active_job.id).all()
        total_count = len(candidates)
        terminal = {CandStatus.SHORTLISTED, CandStatus.REVIEWED, CandStatus.REJECTED, CandStatus.UNGRADED, "Processed"}
        processed_count = sum(1 for c in candidates if c.status in terminal)
        scored = [c for c in candidates if c.status in (CandStatus.SHORTLISTED, CandStatus.REVIEWED, "Processed")]
        avg_score = sum(c.total_score for c in scored) / max(1, len(scored))
        high_matches = sum(1 for c in candidates if c.status in (CandStatus.SHORTLISTED, "Processed") and c.total_score >= 70.0)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{total_count}</div>
                <div class="metric-label">Job Applicants</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{processed_count}</div>
                <div class="metric-label">Processed</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{avg_score:.1f}</div>
                <div class="metric-label">Average Score</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{high_matches}</div>
                <div class="metric-label">High Matches (>=70)</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)

        # 5. Leaderboard Section
        st.header(f"🏆 Candidate Rankings - {active_job.title}")
        
        if not candidates:
            st.info("No candidates uploaded for this job yet. Use the sidebar to upload PDF resumes or run the updated `test_scoring.py` script to generate candidates.")
            return

        # Prepare Leaderboard DataFrame
        leaderboard_data = []
        for rank, cand in enumerate(db.query(Candidate).filter(Candidate.job_id == active_job.id).order_by(Candidate.total_score.desc()).all(), 1):
            name = cand.name if cand.name else cand.filename.replace("_Resume.pdf", "").replace("_", " ")
            leaderboard_data.append({
                "ID": cand.id,
                "Rank": rank,
                "Candidate Name": name,
                "Email": cand.email or "N/A",
                "Total Score": cand.total_score,
                "Tier 1 (Intake/Rules)": cand.tier1,
                "Tier 2 (Semantic JD)": cand.tier2,
                "Tier 3 (LLM Eval)": cand.tier3,
                "Status": cand.status,
                "Filename": cand.filename
            })
            
        df = pd.DataFrame(leaderboard_data)
        
        # Filtering Tools

        # ---- Re‑process pending resumes ----
        if st.button("🔄 Re‑process pending resumes"):
            pending = db.query(Candidate).filter(
                Candidate.job_id == active_job.id,
                Candidate.status.in_([CandStatus.QUEUED, CandStatus.PROCESSING, "Pending"])
            ).all()
            if not pending:
                st.info("No pending resumes to process for this job.")
            else:
                # Ensure executor exists

                pending_futures = []
                for cand in pending:
                    # Submit scoring for each pending candidate
                    # Open a fresh DB session for each candidate and ensure it closes after processing
                    def _process_candidate(cid):
                        db = SessionLocal()
                        try:
                            evaluate_candidate_pipeline(cid, db)
                        finally:
                            db.close()
                    future = st.session_state.scoring_executor.submit(_process_candidate, cand.id)
                    pending_futures.append((cand.filename, future))
                # Progress UI for pending
                progress = st.progress(0)
                placeholder = st.empty()
                total = len(pending_futures)
                for idx, (fname, fut) in enumerate(pending_futures, start=1):
                    while not fut.done():
                        placeholder.info(f"Scoring pending '{fname}' ... ({idx}/{total})")
                        time.sleep(0.5)
                    try:
                        fut.result()
                        st.success(f"Processed & Scored: {fname}")
                    except Exception as err:
                        st.error(f"Scoring failed for {fname}: {err}")
                    progress.progress(int(idx / total * 100))
                st.rerun()
        
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            min_score = st.slider("Filter by Minimum Total Score:", 0.0, 100.0, 0.0)
        with filter_col2:
            status_filter = st.multiselect(
                "Filter by Status:",
                options=[
                    CandStatus.SHORTLISTED, CandStatus.REVIEWED, CandStatus.REJECTED,
                    CandStatus.UNGRADED, CandStatus.QUEUED, CandStatus.PROCESSING,
                    CandStatus.ERROR, "Processed", "Pending", "Failed",
                ],
                default=[CandStatus.SHORTLISTED, CandStatus.REVIEWED, CandStatus.QUEUED],
            )
            
        filtered_df = df[(df["Total Score"] >= min_score) & (df["Status"].isin(status_filter))]
        
        # Display Leaderboard
        st.dataframe(
            filtered_df[["Rank", "Candidate Name", "Email", "Total Score", "Tier 1 (Intake/Rules)", "Tier 2 (Semantic JD)", "Tier 3 (LLM Eval)", "Status"]],
            use_container_width=True,
            hide_index=True
        )

        # Export Actions
        export_col1, export_col2 = st.columns(2)
        with export_col1:
            if config.get("dashboard", {}).get("export_csv", True):
                csv = filtered_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Leaderboard to CSV",
                    data=csv,
                    file_name=f"ai_recruiter_{active_job.title.lower().replace(' ', '_')}_leaderboard.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        with export_col2:
            # Generate markdown recruitment report
            report_md = []
            report_md.append(f"# 💼 EXECUTIVE RECRUITMENT REPORT: {active_job.title} ({active_job.department})")
            report_md.append(f"**Generated At:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            report_md.append("\n---\n")
            report_md.append(f"## 📋 Job Profile Status: {active_job.status}")
            report_md.append("\n**Target Job Description:**")
            report_md.append(f"> {active_job.job_description}\n")

            total = len(filtered_df)
            passed = sum(1 for _, r in filtered_df.iterrows() if r["Status"] == "Processed")
            failed = total - passed
            avg_score = filtered_df[filtered_df["Status"] == "Processed"]["Total Score"].mean() if passed > 0 else 0

            report_md.append("### 📊 Metrics Summary")
            report_md.append(f"- **Total Applicants:** {total}")
            report_md.append(f"- **Passed Screening:** {passed}")
            report_md.append(f"- **Failed Screening:** {failed}")
            report_md.append(f"- **Average Processed Score:** {avg_score:.1f}/100\n")

            report_md.append("### 🏆 Candidate Rankings")
            report_md.append("| Rank | Candidate Name | Email | Total Score | Tier 1 (Rules) | Tier 2 (Semantic) | Tier 3 (LLM) | Status |")
            report_md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            
            for idx, row in filtered_df.iterrows():
                report_md.append(
                    f"| {row['Rank']} | {row['Candidate Name']} | `{row['Email']}` | **{row['Total Score']:.1f}** | {row['Tier 1 (Intake/Rules)']:.1f} | {row['Tier 2 (Semantic JD)']:.1f} | {row['Tier 3 (LLM Eval)']:.1f} | {row['Status']} |"
                )
            report_md.append("\n")

            report_md.append("### 🔍 Qualitative Analysis")
            candidates_detailed = db.query(Candidate).filter(Candidate.job_id == active_job.id).order_by(Candidate.total_score.desc()).all()
            for cand in candidates_detailed:
                if cand.status != "Processed":
                    continue
                name = cand.name if cand.name else cand.filename.replace("_Resume.pdf", "").replace("_", " ")
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
            
            report_content = "\n".join(report_md).encode('utf-8')
            
            st.download_button(
                label="📄 Export Executive Report (Markdown)",
                data=report_content,
                file_name=f"ai_recruiter_{active_job.title.lower().replace(' ', '_')}_report.md",
                mime="text/markdown",
                use_container_width=True
            )
        
        st.markdown("---")
        
        # 6. Detail Expanded Row View
        st.header("🔍 Candidate Deep-Dive")
        
        candidate_options = {f"{c['Candidate Name']} ({c['Total Score']} pts)": c['ID'] for c in leaderboard_data}
        selected_option = st.selectbox("Select a candidate to examine details:", options=list(candidate_options.keys()))
        
        if selected_option:
            cand_id = candidate_options[selected_option]
            cand = db.query(Candidate).filter(Candidate.id == cand_id).first()
            
            if cand:
                col_left, col_right = st.columns([1, 1])
                
                with col_left:
                    st.subheader("📊 Score Breakdown")
                    st.write(f"**Email Detected**: `{cand.email or 'N/A'}`")
                    st.write(f"**Filename**: `{cand.filename}`")
                    st.write(f"**Ingested on**: `{cand.created_at or 'N/A'}`")
                    
                    # Tier Breakdowns
                    st.markdown(f"**Tier 1: Profile Rules** : `{cand.tier1} / 30`")
                    st.progress(cand.tier1 / 30.0)
                    st.caption("Contact details presence & Section coverage")
                    
                    st.markdown(f"**Tier 2: Semantic JD Similarity** : `{cand.tier2} / 40`")
                    st.progress(cand.tier2 / 40.0)
                    st.caption("Local Sentence-Transformers semantic match")
                    
                    st.markdown(f"**Tier 3: LLM Qualitative Fit** : `{cand.tier3} / 30`")
                    st.progress(cand.tier3 / 30.0)
                    st.caption("Llama3 qualitative evaluation score via Groq")
                    
                    st.markdown(f"### **Consolidated Total**: `{cand.total_score} / 100`")
                    
                with col_right:
                    st.subheader("💡 LLM Evaluation Insights")
                    if cand.summary:
                        st.markdown(f"""
                        <div class="detail-container">
                            <h4>Executive Summary</h4>
                            <p>{cand.summary}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("LLM summary is not available for this candidate.")
                        
                    st.markdown("#### **Extracted Evidence**")
                    if cand.evidence:
                        try:
                            evidences = json.loads(cand.evidence)
                            for ev in evidences:
                                st.markdown(f"- {ev}")
                        except Exception:
                            st.write(cand.evidence)
                    else:
                        st.caption("No concrete evidence items processed.")
                
                # Raw Text Viewer (Expander)
                if config.get("dashboard", {}).get("show_raw_resume", True):
                    with st.expander("📄 View Raw Extracted Resume Text"):
                        st.code(cand.raw_text, language="text")
                    
    finally:
        db.close()

# ---------------------------------------------------------------------
# Email utility – uses SMTP credentials from .env (Gmail example)
# ---------------------------------------------------------------------

def send_email(to_address: str, subject: str, body: str) -> None:
    """Send a simple plain‑text email via Gmail's SMTP server.

    Args:
        to_address: Recipient email address.
        subject: Email subject line.
        body: Plain‑text email body.
    """
    # Load .env from project root (three levels up from this file)
    load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')))
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_email or not smtp_password:
        raise RuntimeError("SMTP credentials not configured in .env")
        
    msg = EmailMessage()
    msg["From"] = smtp_email
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    # Gmail SMTP – TLS
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(msg)

if __name__ == "__main__":
    main()
