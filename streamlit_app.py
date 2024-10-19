import streamlit as st
from scheduler import InteractiveGroupScheduler
from sidebar import sidebar
from utils import update_members_from_sheet, export_meetings_to_sheets
from config import DATA_FILE
import pandas as pd
from datetime import datetime
from collections import defaultdict
from streamlit_gsheets import GSheetsConnection
import io
from utils import update_members_from_sheet, export_meetings_to_sheets, import_members_from_file

def main():
    st.set_page_config(layout="wide")

    if 'scheduler' not in st.session_state:
        st.session_state.scheduler = InteractiveGroupScheduler()
    scheduler = st.session_state.scheduler

    if 'page' not in st.session_state:
        st.session_state.page = "Hovedside"

    st.sidebar.title("Navigation")
    
    if st.sidebar.button("Hovedside >", key="nav_hovedside"):
        st.session_state.page = "Hovedside"
    if st.sidebar.button("Quick shuffle af mødegrupper >", key="nav_shuffle"):
        st.session_state.page = "Shuffle Mødegrupper"
    
    st.sidebar.markdown("---")

    st.title("Gruppeinddeling")

    if st.session_state.page == "Hovedside":
        main_page(scheduler)
    elif st.session_state.page == "Statistik":
        statistics_page(scheduler)
    else:
        shuffle_groups_page(scheduler)

def main_page(scheduler):
    sidebar(scheduler)

    st.header("Opret nyt møde")

    st.markdown('<h3 style="color:red;">STEP 1</h3>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload Excel eller CSV fil", type=['csv', 'xlsx', 'xls'], key="file_uploader_main")
    if uploaded_file is not None:
        st.markdown('<h3 style="color:red;">STEP 2</h3>', unsafe_allow_html=True)
        if st.button("Importer fra fil", key="import_button_main"):
            success, message = import_members_from_file(scheduler, uploaded_file)
            if success:
                st.success(message)
            else:
                st.error(message)

    st.markdown('<h3 style="color:red;">STEP 3</h3>', unsafe_allow_html=True)
    meeting_date = st.date_input("Vælg mødedato", value=datetime.now(), key="meeting_date_input_main")
    
    st.markdown('<h3 style="color:red;">STEP 4</h3>', unsafe_allow_html=True)
    st.subheader("Vælg deltagere fra bruttoliste")

    if st.button("Ryd deltagere", key="clear_participants_button_main"):
        scheduler.remove_all_participants()
        st.session_state.clear()
        st.success("Alle deltagere er blevet fjernet.")
        st.rerun()
    
    for group_index, group in enumerate(sorted(scheduler.group_affiliations)):
        with st.expander(f"{group} ({len([p for p in scheduler.participants if group in p.get('groups', [])])} medlemmer)", key=f"group_expander_main_{group_index}"):
            all_selected = st.checkbox(f"Vælg alle i {group}", value=True, key=f"select_all_main_{group_index}")
            
            for i, participant in enumerate([p for p in scheduler.participants if group in p.get('groups', [])]):
                name = participant.get('name', 'Unavngivet')
                if st.checkbox(name, key=f"checkbox_main_{group_index}_{i}", value=all_selected):
                    if 'bruttoliste' not in st.session_state:
                        st.session_state.bruttoliste = []
                    if name not in st.session_state.bruttoliste:
                        st.session_state.bruttoliste.append(name)
                elif name in st.session_state.get('bruttoliste', []):
                    st.session_state.bruttoliste.remove(name)

    st.subheader("Bruttoliste")
    if st.button("Ryd bruttoliste", key="clear_bruttoliste_button_main"):
        if 'bruttoliste' in st.session_state:
            st.session_state.bruttoliste = []
        for key in list(st.session_state.keys()):
            if key.startswith("checkbox_") or key.startswith("select_all_"):
                st.session_state[key] = False
        st.rerun()

    with st.expander("Se bruttoliste", key="bruttoliste_expander_main"):
        if st.session_state.get('bruttoliste'):
            col1, col2 = st.columns(2)
            for i, participant in enumerate(st.session_state.bruttoliste):
                if i % 2 == 0:
                    col1.write(f"- {participant}")
                else:
                    col2.write(f"- {participant}")
            st.write(f"Antal valgte deltagere: {len(st.session_state.bruttoliste)}")
        else:
            st.write("Ingen deltagere valgt endnu.")

    st.markdown('<h3 style="color:red;">STEP 5</h3>', unsafe_allow_html=True)
    st.subheader("Foreslå grupper")
    
    group_size = st.selectbox("Vælg antal personer per gruppe", [3, 4, 5, 6], index=1, key="group_size_select_main")
    
    if st.button("Foreslå grupper", key="suggest_groups_button_main"):
        if st.session_state.get('bruttoliste'):
            suggested_groups, unassigned_count = scheduler.shuffle_groups(group_size)
            if suggested_groups:
                st.session_state.suggested_groups = suggested_groups
                st.session_state.unassigned_count = unassigned_count
                st.success(f"Grupper er blevet foreslået. {unassigned_count} deltagere kunne ikke fordeles optimalt.")
            else:
                st.error("Der opstod en fejl under forslag af grupper.")
        else:
            st.warning("Tilføj deltagere til bruttolisten før du foreslår grupper.")

    if 'suggested_groups' in st.session_state:
        st.subheader("Foreslåede grupper")
        for i, group in enumerate(st.session_state.suggested_groups):
            group_str = f"Gruppe {i+1}:"
            for name in group:
                participant = next((p for p in scheduler.participants if p['name'] == name), None)
                if participant:
                    affiliations = ', '.join(participant.get('groups', ['Ikke tildelt']))
                    group_str += f" {name} ({affiliations}),"
                else:
                    group_str += f" {name} (Ukendt),"
            st.write(group_str.rstrip(','))
        
        if st.session_state.get('unassigned_count', 0) > 0:
            st.write(f"Antal deltagere, der ikke kunne fordeles optimalt: {st.session_state.unassigned_count}")

        st.markdown('<h3 style="color:red;">STEP 6</h3>', unsafe_allow_html=True)
        if st.button("Opret møde med disse grupper", key="create_meeting_button_main"):
            meeting_name = scheduler.create_meeting(st.session_state.suggested_groups, str(meeting_date))
            st.success(f"Møde '{meeting_name}' oprettet for {meeting_date} med de foreslåede grupper.")
            scheduler.save_data()
            del st.session_state.suggested_groups
            st.rerun()

    if scheduler.meetings:
        st.header("Senest oprettet møde")
        latest_meeting = scheduler.meetings[-1]
        with st.expander(f"{latest_meeting.get('name', 'Ukendt navn')} ({latest_meeting.get('date', 'Ingen dato angivet')})", key="latest_meeting_expander_main"):
            st.write("Grupper:")
            for i, group in enumerate(latest_meeting['groups']):
                group_str = f"Gruppe {i+1}:"
                for name in group:
                    participant = next((p for p in scheduler.participants if p['name'] == name), None)
                    if participant:
                        affiliations = ', '.join(participant.get('groups', ['Ikke tildelt']))
                        group_str += f" {name} ({affiliations}),"
                    else:
                        group_str += f" {name} (Ukendt),"
                st.write(group_str.rstrip(','))
            
            if st.button("Rediger grupper for det seneste møde", key="edit_latest_meeting_button_main"):
                st.session_state.editing_meeting = len(scheduler.meetings) - 1
                st.session_state.manual_groups, st.session_state.unassigned = scheduler.manual_group_matching(
                    [p for group in latest_meeting['groups'] for p in group],
                    latest_meeting['groups']
                )
                st.rerun()
            
            if st.button("Slet det seneste møde", key="delete_latest_meeting_button_main"):
                if scheduler.delete_meeting(len(scheduler.meetings) - 1):
                    st.success("Det seneste møde er blevet slettet.")
                    st.rerun()
                else:
                    st.error("Der opstod en fejl ved sletning af mødet.")

        if len(scheduler.meetings) > 1:
            st.header("Tidligere møder")
            for meeting_index, meeting in enumerate(reversed(scheduler.meetings[:-1])):
                with st.expander(f"{meeting.get('name', 'Ukendt navn')} ({meeting.get('date', 'Ingen dato angivet')}, {sum(len(group) for group in meeting['groups'])} deltagere)", key=f"previous_meeting_expander_main_{meeting_index}"):
                    st.write("Grupper:")
                    for j, group in enumerate(meeting['groups']):
                        st.write(f"Gruppe {j+1}: {', '.join(group)}")
                    
                    if st.button(f"Rediger grupper", key=f"edit_meeting_button_main_{meeting_index}"):
                        st.session_state.editing_meeting = scheduler.meetings.index(meeting)
                        st.session_state.manual_groups, st.session_state.unassigned = scheduler.manual_group_matching(
                            [p for group in meeting['groups'] for p in group],
                            meeting['groups']
                        )
                        st.rerun()
                    
                    if st.button(f"Slet møde", key=f"delete_meeting_button_main_{meeting_index}"):
                        if scheduler.delete_meeting(scheduler.meetings.index(meeting)):
                            st.success(f"Mødet er blevet slettet.")
                            st.rerun()
                        else:
                            st.error("Der opstod en fejl ved sletning af mødet.")

    if 'editing_meeting' in st.session_state:
        st.subheader(f"Rediger grupper for møde {st.session_state.editing_meeting + 1}")
        cols = st.columns(len(st.session_state.manual_groups) + 1)
        
        for i, group in enumerate(st.session_state.manual_groups):
            cols[i].write(f"Gruppe {i+1}")
            for person in group:
                if cols[i].button(f"Fjern {person}", key=f"remove_person_button_main_{i}_{person}"):
                    st.session_state.manual_groups[i].remove(person)
                    st.session_state.unassigned.append(person)
                    st.rerun()
        
        cols[-1].write("Ikke tildelt")
        for person in st.session_state.unassigned:
            col = cols[-1].selectbox(f"Tildel {person}", ["Ikke tildelt"] + [f"Gruppe {i+1}" for i in range(len(st.session_state.manual_groups))], key=f"assign_person_select_main_{person}")
            if col != "Ikke tildelt":
                group_index = int(col.split()[-1]) - 1
                st.session_state.manual_groups[group_index].append(person)
                st.session_state.unassigned.remove(person)
                st.rerun()
        
        if st.button("Gem ændringer", key="save_changes_button_main"):
            scheduler.update_meeting_groups(st.session_state.editing_meeting, st.session_state.manual_groups)
            del st.session_state.editing_meeting
            del st.session_state.manual_groups
            del st.session_state.unassigned
            st.rerun()

def statistics_page(scheduler):
    st.header("Statistik")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Antal deltagelser per person")
        participation_stats = scheduler.get_participation_stats()
        for name, count in sorted(participation_stats.items(), key=lambda x: x[1], reverse=True):
            participant = next((p for p in scheduler.participants if p['name'] == name), None)
            if participant:
                groups = ', '.join(participant.get('groups', ['Ikke tildelt']))
                st.write(f"{name} ({groups}): {count} møde(r)")

    with col2:
        st.subheader("Grupperinger per person")
        participant_names = [p['name'] for p in scheduler.participants]
        selected_participant = st.selectbox("Vælg deltager", options=participant_names, key="participant_select_stats")
        if selected_participant:
            participant = next((p for p in scheduler.participants if p['name'] == selected_participant), None)
            if participant:
                groups = ', '.join(participant.get('groups', ['Ikke tildelt']))
                st.write(f"Tilhørsgruppe(r): {groups}")
                grouping_stats = scheduler.get_grouping_stats(selected_participant)
                for other, count in sorted(grouping_stats.items(), key=lambda x: x[1], reverse=True):
                    other_participant = next((p for p in scheduler.participants if p['name'] == other), None)
                    if other_participant:
                        other_groups = ', '.join(other_participant.get('groups', ['Ikke tildelt']))
                        st.write(f"{other} ({other_groups}): {count} gang(e)")

def shuffle_groups_page(scheduler):
    st.header("Shuffle Mødegrupper")

    st.subheader("Upload medlemmer")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<h3 style="color:red;">STEP 1</h3>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload Excel eller CSV fil", type=['csv', 'xlsx', 'xls'], key="file_uploader_shuffle")
        st.markdown('<h3 style="color:red;">STEP 2</h3>', unsafe_allow_html=True)
        if uploaded_file is not None:
            if st.button("Importer fra fil", key="import_button_shuffle"):
                success, message = import_members_from_file(scheduler, uploaded_file)
                if success:
                    st.success(message)
                else:
                    st.error(message)

    st.markdown('<h3 style="color:red;">STEP 3</h3>', unsafe_allow_html=True)
    group_size = st.selectbox("Vælg antal personer per gruppe", [3, 4, 5, 6], index=1, key="group_size_select_shuffle")

    st.subheader("Importerede medlemmer")

    st.markdown('<h3 style="color:red;">STEP 4</h3>', unsafe_allow_html=True)
    if st.button("Shuffle mødegrupper", key="shuffle_groups_button"):
        shuffled_groups = scheduler.shuffle_groups(group_size)
        st.session_state.shuffled_groups = shuffled_groups

    if st.button("Ryd deltagere", key="clear_participants_button_shuffle"):
        scheduler.remove_all_participants()
        st.session_state.clear()
        st.success("Alle deltagere er blevet fjernet.")
        st.rerun()

    members_list = ["Importerede medlemmer"] + [
        f"{participant['name']} - {participant['company']} - {', '.join(participant['groups'])}"
        for participant in scheduler.participants
    ]
    
    selected_member = st.selectbox("Medlemsliste", members_list, key="member_select_shuffle")

    if 'shuffled_groups' in st.session_state:
        st.subheader("Shufflede mødegrupper")
        for i, group in enumerate(st.session_state.shuffled_groups, 1):
            group_members = ', '.join(participant.get('name', 'Unavngivet') for participant in group)
            st.write(f"Gruppe {i}: {group_members}")

        st.markdown('<h3 style="color:red;">STEP 5</h3>', unsafe_allow_html=True)
        st.subheader("Download mødegrupper")
        
        if st.button("Download mødegrupper", key="download_groups_button"):
            csv = scheduler.export_groups_to_csv(st.session_state.shuffled_groups)
            st.download_button(
                label="Download CSV fil",
                data=csv,
                file_name="modegrupper.csv",
                mime="text/csv",
                key="download_csv_button"
            )

def create_pdf(scheduler, groups, meeting_date):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        pdf.cell(200, 10, txt=f"Mødegrupper for {meeting_date}", ln=1, align='C')
        
        for i, group in enumerate(groups, 1):
            pdf.cell(200, 10, txt=f"Gruppe {i}", ln=1)
            for participant in group:
                participant_name = participant if isinstance(participant, str) else participant.get('name', 'Unavngivet')
                participant_data = next((p for p in scheduler.participants if p['name'] == participant_name), None)
                if participant_data:
                    pdf.cell(200, 10, txt=f"  {participant_name} - {participant_data.get('email', 'Ikke angivet')} - {participant_data.get('company', 'Ikke angivet')} - {', '.join(participant_data.get('groups', ['Ikke tildelt']))}", ln=1)
                pdf.cell(200, 10, txt="", ln=1)  # Add an empty line between groups
        
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        st.error(f"Fejl ved oprettelse af PDF: {str(e)}")
        return None

if __name__ == "__main__":
    main()
