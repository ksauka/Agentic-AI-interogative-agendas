"""Anthrokit-inspired visual styling shared by every experimental app."""


def apply_anthrokit_theme(st) -> None:
    """Apply only condition-neutral styling to avoid affecting manipulations."""
    st.markdown(
        """
        <style>
        .stApp {
            background: #ffffff;
            color: #262730;
        }
        /* Anthrokit reading-column width  -  860 px matches anthrokit/anthrokit/stylizer.py */
        .block-container {
            max-width: 1100px;
            padding-top: 2rem;
            padding-bottom: 3rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }
        .study-banner {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.2rem 1.35rem;
            border-radius: 15px;
            margin: 0 0 1.35rem 0;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.10);
        }
        .study-banner h1 {
            color: white;
            font-size: 1.7rem;
            line-height: 1.2;
            margin: 0;
            padding: 0;
        }
        .study-banner p {
            color: rgba(255, 255, 255, 0.93);
            margin: 0.4rem 0 0 0;
            font-size: 0.95rem;
        }
        [data-testid="stSidebar"] {
            background-color: #f0f2f6;
            border-right: 1px solid #e0e0e0;
        }
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #343a40;
        }
        h1, h2, h3 {
            color: #262730;
        }
        [data-testid="stButton"] button[kind="primary"],
        [data-testid="stFormSubmitButton"] button[kind="primary"] {
            background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
            border: 0;
            border-radius: 8px;
            color: white;
            box-shadow: 0 2px 4px rgba(0, 123, 255, 0.20);
        }
        [data-testid="stButton"] button[kind="primary"]:hover,
        [data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
            background: #0056b3;
            color: white;
        }
        [data-testid="stAlert"] {
            border-radius: 10px;
            border-left-width: 4px;
        }
        [data-testid="stExpander"],
        [data-testid="stFileUploaderDropzone"] {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 10px;
        }
        [data-testid="stFileUploaderDropzone"] button {
            border-color: #007bff;
            color: #007bff;
            border-radius: 8px;
        }
        [data-testid="stRadio"] > label,
        [data-testid="stTextInput"] > label,
        [data-testid="stTextArea"] > label,
        [data-testid="stFileUploader"] > label {
            font-weight: 600;
            color: #495057;
        }
        textarea, input {
            border-radius: 8px !important;
        }
        hr {
            border-color: #e9ecef;
        }
        .reference-note {
            background: #f8f9fa;
            border-left: 4px solid #007bff;
            border-radius: 8px;
            padding: 0.75rem 0.85rem;
            margin-bottom: 1rem;
            color: #495057;
        }
        /* Chat bubbles fill full column width */
        [data-testid="stChatMessage"] p {
            line-height: 1.75;
        }
        div[data-testid="stChatMessageContent"] {
            max-width: 100% !important;
        }
        /* Hide Streamlit branding */
        .viewerBadge_container__r5tak { display: none !important; }
        footer { visibility: hidden; }
        #MainMenu { visibility: hidden; }
        /* Completion card */
        .completion-card {
            background: #f0fdf4;
            border: 1px solid #86efac;
            border-radius: 12px;
            padding: 1.5rem 1.75rem;
            margin-bottom: 1.5rem;
        }
        .completion-card h2 {
            color: #166534;
            margin: 0 0 0.4rem;
        }
        .completion-card p {
            color: #15803d;
            margin: 0;
        }
        /* Section header dividers */
        h2 {
            border-bottom: 1px solid #e9ecef;
            padding-bottom: 0.4rem;
            margin-bottom: 1.2rem;
        }
        /* Consistent table styling */
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95rem;
        }
        th {
            background: #f8f9fa;
            font-weight: 600;
            text-align: left;
            padding: 0.5rem 0.75rem;
            border-bottom: 2px solid #dee2e6;
        }
        td {
            padding: 0.45rem 0.75rem;
            border-bottom: 1px solid #f0f0f0;
            vertical-align: top;
        }
        /* Citation chip buttons - compact inline style */
        [data-testid="stButton"] button:not([kind="primary"]) {
            font-size: 0.78rem;
            padding: 0.2rem 0.55rem;
            border-radius: 4px;
            border: 1px solid #c7d2fe;
            background: #eef2ff;
            color: #3730a3;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_study_banner(st) -> None:
    """Display a neutral header styled like the Anthrokit introduction card."""
    st.markdown(
        """
        <div class="study-banner">
            <h1>AI Hiring Decision Assistant</h1>
            <p>Recruiter screening study | Retrieval-grounded decision support</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_study_progress(st, stage: int) -> None:
    """Show a compact step progress bar  -  hidden on Welcome (0) and Complete (9) screens."""
    # Map stage numbers to (step_index, label)  -  only stages that render real screens
    _STEPS = [
        (2, "Role description"),
        (3, "Screening policy"),
        (4, "Candidate review"),
        (7, "Final decision"),
    ]
    active = None
    for i, (s, _) in enumerate(_STEPS):
        if stage >= s:
            active = i
    if active is None:
        return  # Stage 0 (welcome) or unrecognised  -  no progress bar
    total = len(_STEPS)
    step_num = active + 1
    label = _STEPS[active][1]
    st.progress(step_num / total, text=f"Step {step_num} of {total}: {label}")
