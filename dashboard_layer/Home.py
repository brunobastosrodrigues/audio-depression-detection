"""IHearYou dashboard entry point.

Defines the grouped sidebar navigation (st.navigation, Streamlit 1.55) and runs the
selected page. Page content lives in pages/*.py; the landing is pages/00_Home.py.

NOTE: st.set_page_config is called ONCE here. Individual pages must NOT call it (under
st.navigation the entry + the selected page run in the same script pass, so a second
call raises StreamlitSetPageConfigMustBeFirstCommandError).
"""

import streamlit as st

from utils.setup_db import setup_indexes

st.set_page_config(page_title="IHearYou", page_icon="🧠", layout="wide")


# Ensure indexes ONCE per process (cache_resource persists across reruns/sessions).
@st.cache_resource(show_spinner=False)
def _ensure_indexes_once():
    try:
        setup_indexes()
    except Exception as e:
        print(f"Index setup failed (expected if DB is not ready): {e}")
    return True


_ensure_indexes_once()

# Grouped navigation. Dict keys are sidebar section headers; order = display order.
# st.Page(title=...) sets BOTH the sidebar label and the browser-tab title, so naming
# is consistent centrally without editing each page's in-page st.title().
# Operator-primary: to put Fleet above My Wellbeing, move the "Fleet" block up.
pages = {
    " ": [  # ungrouped, top of the sidebar (no visible header)
        st.Page("pages/00_Home.py", title="Home", icon="🏠", default=True),
    ],
    "My Wellbeing": [
        st.Page("pages/1_Overview.py",    title="Overview",    icon="💚"),
        st.Page("pages/2_Indicators.py",  title="Indicators",  icon="📊"),
        st.Page("pages/3_Trends.py",      title="Trends",      icon="📈"),
        st.Page("pages/4_Self_Report.py", title="Self-Report", icon="📝"),
    ],
    "Fleet": [
        st.Page("pages/12_Fleet_Health.py", title="Fleet Health",   icon="🩺"),
        st.Page("pages/5_Boards.py",        title="Boards & Rooms", icon="📡"),
        st.Page("pages/10_Edge_Nodes.py",   title="Edge Nodes",     icon="🔌"),
    ],
    "Admin": [
        st.Page("pages/8_User_Management.py",      title="Users & Enrollment",  icon="👥"),
        st.Page("pages/7_Data_Tools.py",           title="Data Tools",          icon="🔧"),
        st.Page("pages/9_Scene_Forensics.py",      title="Scene Analysis",      icon="🔬"),
        st.Page("pages/6_Settings.py",             title="Settings",            icon="⚙️"),
        st.Page("pages/11_Research_Validation.py", title="Research Validation", icon="🧪"),
    ],
}

st.navigation(pages).run()
