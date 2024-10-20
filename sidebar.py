import streamlit as st
from collections import defaultdict
from streamlit_gsheets import GSheetsConnection
from utils import update_members_from_sheet, export_meetings_to_sheets

# Variabler til at kontrollere synligheden af sektionerne
SHOW_SHEET_DATA = False  # Skjul "Deltagerhåndtering" og Google Sheets
SHOW_REMOVE_MEMBERS = False  # Skjul "Fjern alle medlemmer"

def sidebar(scheduler):
    st.sidebar.title("Navigation")
    
    if st.sidebar.button("Hovedside >", key="nav_hovedside"):
        st.session_state.page = "Hovedside"

    # Skjuler deltagerhåndtering, hvis SHOW_SHEET_DATA er False
    if SHOW_SHEET_DATA:  
        st.sidebar.header("Deltagerhåndtering")
        display_sheet_data(scheduler)

    # Skjuler sektionen for at fjerne alle medlemmer, hvis SHOW_REMOVE_MEMBERS er False
    if SHOW_REMOVE_MEMBERS:  
        remove_all_members(scheduler)

    display_current_members(scheduler)

    st.sidebar.markdown("---")  # Horizontal line

    handle_import_export(scheduler)

    st.sidebar.markdown("---")  # Horizontal line

    add_new_participant(scheduler)

    st.sidebar.markdown("---")  # Horizontal line

    create_group_affiliation(scheduler)

# Funktionen for "Fjern alle medlemmer", som er skjult
def remove_all_members(scheduler):
    with st.sidebar.expander("Fjern alle medlemmer"):
        st.write("Advarsel: Dette vil fjerne alle medlemmer fra programmet, men ikke fra Google Sheets.")
        if st.button("Fjern alle medlemmer", key="remove_all_members"):
            confirm = st.checkbox("Er du sikker? Denne handling kan ikke fortrydes.", key="confirm_remove_all")
            if confirm:
                scheduler.remove_all_participants()
                st.success("Alle medlemmer er blevet fjernet fra programmet.")
                st.rerun()

# Funktionen for "Medlemsdata fra Google Sheets", som er skjult
# def display_sheet_data(scheduler):
#     st.sidebar.subheader("Medlemsdata fra Google Sheets")
    
#     conn = st.connection("gsheets", type=GSheetsConnection)
#     df = conn.read()
    
#     st.sidebar.write(f"Antal rækker i Google Sheet: {len(df)}")
#     st.sidebar.write(f"Kolonner: {', '.join(df.columns)}")

#     if st.sidebar.button("Importér medlemmer fra Google Sheet", key="update_members"):
#         try:
#             success, message = update_members_from_sheet(scheduler, df)
#             if success:
#                 st.sidebar.success(message)
#             else:
#                 st.sidebar.error(message)
#         except Exception as e:
#             st.sidebar.error(f"Der opstod en fejl under opdatering af medlemmer: {str(e)}")

def remove_all_members(scheduler):
    with st.sidebar.expander("Fjern alle medlemmer"):
        st.write("Advarsel: Dette vil fjerne alle medlemmer fra programmet, men ikke fra Google Sheets.")
        if st.button("Fjern alle medlemmer", key="remove_all_members"):
            confirm = st.checkbox("Er du sikker? Denne handling kan ikke fortrydes.", key="confirm_remove_all")
            if confirm:
                scheduler.remove_all_participants()
                st.success("Alle medlemmer er blevet fjernet fra programmet.")
                st.rerun()

def display_current_members(scheduler):
    st.sidebar.markdown("---")  # Horizontal line
    st.sidebar.subheader("Medlemsliste")
    
    members = []
    for member in scheduler.participants:
        try:
            name = member.get('name', 'Unavngivet')
            groups = member.get('groups', ['Ikke tildelt'])
            member_info = f"{name} - {', '.join(groups)}"
            member_id = member.get('id', '')
            members.append((member_info, member_id))
        except Exception as e:
            st.sidebar.error(f"Fejl ved behandling af medlem: {str(e)}")
    
    if members:
        selected_member_info = st.sidebar.selectbox("Vælg et medlem for at se detaljer", members, format_func=lambda x: x[0])
        if selected_member_info:
            try:
                selected_member = next((m for m in scheduler.participants if m.get('id') == selected_member_info[1]), None)
                if selected_member:
                    st.sidebar.write(f"Navn: {selected_member.get('name', 'Ikke angivet')}")
                    st.sidebar.write(f"Grupper: {', '.join(selected_member.get('groups', ['Ikke tildelt']))}")
                    st.sidebar.write(f"Email: {selected_member.get('email', 'Ikke angivet')}")
                    st.sidebar.write(f"Virksomhed: {selected_member.get('company', 'Ikke angivet')}")
                    st.sidebar.write(f"Stilling: {selected_member.get('position', 'Ikke angivet')}")
                    st.sidebar.write(f"Branche: {selected_member.get('industry', 'Ikke angivet')}")
                else:
                    st.sidebar.warning("Valgt medlem kunne ikke findes.")
            except Exception as e:
                st.sidebar.error(f"Fejl ved visning af medlemsdetaljer: {str(e)}")
    else:
        st.sidebar.write("Ingen medlemmer at vise.")

def handle_import_export(scheduler):
    st.sidebar.subheader("Eksport af data")
    
    if st.sidebar.button("Eksport af medlemsliste", key="export_members"):
        export_participants(scheduler.participants)

    if st.sidebar.button("Eksporter mødedata til Google Sheets", key="export_meetings"):
        success, message = export_meetings_to_sheets(scheduler)
        if success:
            st.sidebar.success(message)
        else:
            st.sidebar.error(message)

    st.sidebar.subheader("Import af data")
    uploaded_file = st.sidebar.file_uploader("Importér deltagere (Excel eller CSV)", type=["xlsx", "csv"], key="file_uploader")
    if uploaded_file is not None:
        if st.sidebar.button("Importér deltagere", key="import_members"):
            import_participants(scheduler, uploaded_file)

def add_new_participant(scheduler):
    with st.sidebar.expander("Tilføj ny deltager", expanded=False):
        full_name = st.text_input("Fulde navn", key="new_participant_name")
        company = st.text_input("Virksomhed", key="new_participant_company")
        position = st.text_input("Stilling", key="new_participant_position")
        industry = st.text_input("Branche", key="new_participant_industry")
        group = st.selectbox("Gruppetilhør", options=[""] + list(scheduler.group_affiliations), key="new_participant_group")
        
        if st.button("Tilføj deltager", key="add_participant"):
            if full_name:
                participant_data = {
                    "name": full_name,
                    "company": company,
                    "position": position,
                    "industry": industry,
                    "groups": [group] if group else [],
                    "meetings": 0,
                    "groupings": {}
                }
                if scheduler.add_participant(full_name, participant_data):
                    st.sidebar.success(f"Deltager '{full_name}' er tilføjet.")
                    st.session_state.clear_inputs = True
                else:
                    st.sidebar.error(f"Kunne ikke tilføje deltager '{full_name}'. Måske eksisterer den allerede?")
            else:
                st.sidebar.error("Deltagerens navn skal udfyldes.")

def create_group_affiliation(scheduler):
    with st.sidebar.expander("Opret nyt gruppetilhør"):
        new_group = st.text_input("Nyt gruppetilhør navn", key="new_group_input")
        if st.button("Opret gruppetilhør", key="create_group"):
            if new_group and new_group not in scheduler.group_affiliations:
                scheduler.add_group_affiliation(new_group)
                st.success(f"Gruppetilhør '{new_group}' er oprettet.")
            else:
                st.error("Gruppetilhør eksisterer allerede eller er tomt.")

def export_participants(participants):
    # Implementation for exporting participants
    pass

def import_participants(scheduler, file):
    # Implementation for importing participants
    pass

__all__ = ['sidebar', 'get_display_name', 'export_meetings_to_sheets']
