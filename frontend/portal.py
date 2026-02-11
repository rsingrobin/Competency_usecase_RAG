import streamlit as st
import requests

# Backend API URL
API = "http://localhost:8001"   # change if using 8000

st.set_page_config(page_title="Employee Competency Portal")

# -------------------------------
# Session initialization
# -------------------------------
if "token" not in st.session_state:
    st.session_state.token = None


# -------------------------------
# Login Screen
# -------------------------------
def login_screen():
    st.title("Employee Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            resp = requests.post(
                f"{API}/login",
                data={"email": email, "password": password},
                timeout=500,
            )
        except Exception as e:
            st.error(f"Connection error: {e}")
            st.stop()

        if resp.status_code != 200:
            st.error("Login failed")
            st.stop()

        data = resp.json()

        if "token" not in data:
            st.error("Invalid credentials")
            st.stop()

        st.session_state.token = data["token"]
        st.rerun()

def advisor_chat(headers):
    st.subheader("AI Competency Advisor")

    question = st.text_input(
        "Ask about competencies or learning path"
    )

    if st.button("Ask Advisor"):
        try:
            resp = requests.get(
                f"{API}/advisor",
                params={"question": question},
                headers=headers,
                timeout=600,
            )

            resp.raise_for_status()
            data = resp.json()

            st.write(data["answer"])

        except Exception as e:
            st.error(str(e))


# -------------------------------
# Dashboard
# -------------------------------
def dashboard():
    st.title("My Competencies")

    headers = {
        "Authorization": f"Bearer {st.session_state.token}"
    }

    try:
        resp = requests.get(
            f"{API}/my-competencies",
            headers=headers,
            timeout=500,
        )
        resp.raise_for_status()
        competencies = resp.json()

    except Exception as e:
        st.error(f"Failed to load competencies: {e}")
        return

    # ---------- Competency Tabs ----------
    if not competencies:
        st.info("No competencies assigned.")
    else:
        completed = []
        in_progress = []

        for comp in competencies:
            status = (comp.get("status") or "").lower()
            if status == "completed":
                completed.append(comp)
            else:
                in_progress.append(comp)

        tab1, tab2 = st.tabs(["In Progress", "Completed"])

        with tab1:
            if not in_progress:
                st.info("No competencies in progress.")
            else:
                for comp in in_progress:
                    st.markdown(f"""**{comp['competency_name']}**
- ID: {comp['competency_id']}
- Level: {comp['proficiency_level_name']}
- Status: {comp['status']}
- Progress: {comp.get('progress', 0)} %
---
""")

        with tab2:
            if not completed:
                st.info("No completed competencies.")
            else:
                for comp in completed:
                    st.markdown(f"""**{comp['competency_name']}**
- ID: {comp['competency_id']}
- Level: {comp['proficiency_level_name']}
- Status: {comp['status']}
---
""")

    # ---------- Roadmap ----------
    st.divider()
    roadmap_section(headers)

    # ---------- Advisor ----------
    st.divider()
    advisor_chat(headers)

    # ---------- Logout ----------
    st.divider()
    if st.button("Logout"):
        st.session_state.token = None
        st.rerun()



# -------------------------------
# Start competency
# -------------------------------
def start_competency(comp_id):
    headers = {
    "Authorization": f"Bearer {st.session_state.token}"
    }   

    try:
        resp = requests.post(
            f"{API}/start-competency/{comp_id}",
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        st.success("Competency started")
        st.rerun()

    except Exception as e:
        st.error(str(e))


# -------------------------------
# Learning roadmap
# -------------------------------
def roadmap_section(headers):
    st.subheader("Recommended Learning Roadmap")

    try:
        resp = requests.get(
            f"{API}/learning-roadmap",
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        roadmap = resp.json()

    except Exception as e:
        st.error(f"Roadmap error: {e}")
        return

    if roadmap:
        for step in roadmap:
            st.write(
                f"{step['competency_name']}"
                f"(Level: {step['proficiency_level_name']})"

            )
    else:
        st.info("No recommendations yet.")


# -------------------------------
# App Entry
# -------------------------------
if st.session_state.token is None:
    login_screen()
else:
    dashboard()
