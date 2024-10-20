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

    # Initialiser siden til "Hovedside", hvis den ikke allerede er sat
    if 'page' not in st.session_state:
        st.session_state.page = "Hovedside"

    # Tilføj navigation menu i sidebaren
    # st.sidebar.title("Navigation")
    
    # Erstat dropdown med knapper
    # if st.sidebar.button("Hovedside >"):
        # st.session_state.page = "Hovedside"
    # if st.sidebar.button("Quick shuffle af mødegrupper >"):
        # st.session_state.page = "Shuffle Mødegrupper"
    
    # Skjul statistik-knappen for nu (kan gøres synlig senere)
    # if st.sidebar.button("Statistik >"):
    #     st.session_state.page = "Statistik"
    
    # Tilføj horisontal linje under sidste knap
    # st.sidebar.markdown("---")

    # Tilføj hovedtitel
    st.title("Gruppeinddeling")

    # Vis den valgte side
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
    
    # Initialisér tilstandsvariabler
    if 'members_removed' not in st.session_state:
        st.session_state.members_removed = False
    if 'uploader_key' not in st.session_state:
        st.session_state.uploader_key = 0

    # File uploader med dynamisk nøgle
    uploaded_file = st.file_uploader("Upload Excel eller CSV fil", type=['csv', 'xlsx', 'xls'], key=f"file_uploader_main_{st.session_state.uploader_key}")
    
    if st.button("Fjern alle medlemmer", key="remove_all_members_button"):
        scheduler.remove_all_participants()
        st.session_state.pop('all_suggested_groups', None)
        st.session_state.members_removed = True
        st.session_state.uploader_key += 1  # Ændrer nøglen for at nulstille uploaderen
        st.rerun()

    # Vis notifikation, hvis medlemmer er blevet fjernet
    if st.session_state.members_removed:
        st.success("Alle medlemmer er blevet fjernet. Du kan nu uploade en ny fil.")
        st.session_state.members_removed = False

    if uploaded_file is not None:
        st.markdown('<h3 style="color:red;">STEP 2</h3>', unsafe_allow_html=True)
        if st.button("Importer fra fil", key="import_file_button"):
            success, message = import_members_from_file(scheduler, uploaded_file)
            if success:
                st.success(message)
            else:
                st.error(message)

    # Datovælger for mødet
    st.markdown('<h3 style="color:red;">STEP 3</h3>', unsafe_allow_html=True)
    meeting_date = st.date_input("Vælg mødedato", value=datetime.now(), key="meeting_date_input")
    
    st.markdown('<h3 style="color:red;">STEP 4</h3>', unsafe_allow_html=True)
    st.subheader("Foreslå grupper")
    
    col1, col2 = st.columns(2)
    with col1:
        group_size = st.selectbox("Vælg antal personer per gruppe", [3, 4, 5, 6], index=1, key="group_size_select_main")
    with col2:
        number_of_meetings = st.number_input("Antal møder at oprette", min_value=1, max_value=10, value=1, step=1, key="number_of_meetings_input")
    
    if st.button("Foreslå grupper", key="suggest_groups_button_main"):
        all_suggested_groups = []
        for _ in range(number_of_meetings):
            suggested_groups, _ = scheduler.shuffle_groups(group_size)
            if suggested_groups:
                all_suggested_groups.append(suggested_groups)
            else:
                st.error(f"Der opstod en fejl under forslag af grupper for møde {len(all_suggested_groups) + 1}")
                break
        
        if all_suggested_groups:
            st.session_state.all_suggested_groups = all_suggested_groups
            st.success("Grupper er blevet foreslået. Se nedenfor for detaljer.")
        else:
            st.error("Der opstod en fejl under forslag af grupper.")

    # Vis foreslåede grupper (hvis de findes)
    if 'all_suggested_groups' in st.session_state:
        st.subheader("Foreslåede grupper")
        for meeting_index, suggested_groups in enumerate(st.session_state.all_suggested_groups):
            st.write(f"Møde {meeting_index + 1}:")
            for i, group in enumerate(suggested_groups):
                group_str = f"Gruppe {i+1}:"
                for name in group:
                    participant = next((p for p in scheduler.participants if p['name'] == name), None)
                    if participant:
                        affiliations = ', '.join(participant.get('groups', ['Ikke tildelt']))
                        group_str += f" {name} ({affiliations}),"
                    else:
                        group_str += f" {name} (Ukendt),"
                st.write(group_str.rstrip(','))
            st.write("---")

        st.markdown('<h3 style="color:red;">STEP 5</h3>', unsafe_allow_html=True)
        if st.button("Opret møder med disse grupper", key="create_meetings_button_main"):
            for meeting_index, suggested_groups in enumerate(st.session_state.all_suggested_groups, 1):
                meeting_name = scheduler.create_meeting(suggested_groups, str(meeting_date), meeting_index)
                st.success(f"Møde '{meeting_name}' oprettet for {meeting_date} med de foreslåede grupper.")
            scheduler.save_data()
            del st.session_state.all_suggested_groups
            st.rerun()

    # Vis oprettede møder
    if scheduler.meetings:
        st.header("Oprettede møder")
        for meeting in reversed(scheduler.meetings):
            with st.expander(f"{meeting.get('name', 'Ukendt navn')}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    csv = scheduler.export_meeting_to_csv(meeting)
                    formatted_date = datetime.strptime(meeting['date'], "%Y-%m-%d").strftime("%d-%m-%Y")
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"mode_{meeting.get('meeting_number', meeting['serial'])}_{formatted_date}.csv",
                        mime="text/csv",
                        key=f"download_meeting_{meeting['serial']}_{meeting['date']}"
                    )
                
                with col2:
                    if st.button(f"Rediger grupper", key=f"edit_{meeting['serial']}_{meeting['date']}"):
                        st.session_state.editing_meeting = scheduler.meetings.index(meeting)
                        st.session_state.manual_groups, st.session_state.unassigned = scheduler.manual_group_matching(
                            [p for group in meeting['groups'] for p in group],
                            meeting['groups']
                        )
                        st.rerun()
                
                with col3:
                    if st.button(f"Slet møde", key=f"delete_{meeting['serial']}_{meeting['date']}"):
                        if scheduler.delete_meeting(scheduler.meetings.index(meeting)):
                            st.success(f"Mødet er blevet slettet.")
                            scheduler.reset_meeting_numbers()
                            st.rerun()
                        else:
                            st.error("Der opstod en fejl ved sletning af mødet.")
                
                st.write("Grupper:")
                for j, group in enumerate(meeting['groups']):
                    group_str = f"Gruppe {j+1}:"
                    for name in group:
                        participant = next((p for p in scheduler.participants if p['name'] == name), None)
                        if participant:
                            affiliations = ', '.join(participant.get('groups', ['Ikke tildelt']))
                            group_str += f" {name} ({affiliations}),"
                        else:
                            group_str += f" {name} (Ukendt),"
                    st.write(group_str.rstrip(','))

    # Redigeringssektion for møder
    if 'editing_meeting' in st.session_state:
        st.subheader(f"Rediger grupper for møde {st.session_state.editing_meeting + 1}")
        cols = st.columns(len(st.session_state.manual_groups) + 1)
        
        for i, group in enumerate(st.session_state.manual_groups):
            cols[i].write(f"Gruppe {i+1}")
            for person in group:
                if cols[i].button(f"Fjern {person}", key=f"remove_person_button_{i}_{person}"):
                    st.session_state.manual_groups[i].remove(person)
                    st.session_state.unassigned.append(person)
                    st.rerun()
        
        cols[-1].write("Ikke tildelt")
        for person in st.session_state.unassigned:
            col = cols[-1].selectbox(f"Tildel {person}", ["Ikke tildelt"] + [f"Gruppe {i+1}" for i in range(len(st.session_state.manual_groups))], key=f"assign_person_select_{person}")
            if col != "Ikke tildelt":
                group_index = int(col.split()[-1]) - 1
                st.session_state.manual_groups[group_index].append(person)
                st.session_state.unassigned.remove(person)
                st.rerun()
        
        if st.button("Gem ændringer", key="save_changes_button"):
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
        selected_participant = st.selectbox("Vælg deltager", options=participant_names)
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

    # Upload fra Google Sheets
    st.subheader("Upload medlemmer")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<h3 style="color:red;">STEP 1</h3>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload Excel eller CSV fil", type=['csv', 'xlsx', 'xls'])
        st.markdown('<h3 style="color:red;">STEP 2</h3>', unsafe_allow_html=True)
        if uploaded_file is not None:
            if st.button("Importer fra fil"):
                success, message = import_members_from_file(scheduler, uploaded_file)
                if success:
                    st.success(message)
                else:
                    st.error(message)
    # with col2:
    #     if st.button("Hent medlemmer fra Google Sheets"):
    #         success, message = update_members_from_sheet(scheduler)
    #         if success:
    #             st.success(message)
    #         else:
    #             st.error(message)

    # Vælg antal personer per gruppe
    st.markdown('<h3 style="color:red;">STEP 3</h3>', unsafe_allow_html=True)
    group_size = st.selectbox("Vælg antal personer per gruppe", [3, 4, 5], index=1)

    # Vis importerede medlemmer
    st.subheader("Importerede medlemmer")

    # Shuffle knap
    st.markdown('<h3 style="color:red;">STEP 4</h3>', unsafe_allow_html=True)
    if st.button("Shuffle mødegrupper"):
        shuffled_groups = scheduler.shuffle_groups(group_size)
        st.session_state.shuffled_groups = shuffled_groups

    # Tilføj "Ryd bruttoliste" knap
    # if st.button("Ryd bruttoliste"):
        # scheduler.participants.clear()
        # scheduler.group_affiliations.clear()
        # scheduler.save_data()
        # st.success("Bruttolisten er blevet ryddet.")
        # st.rerun()

    # Tilføj "Ryd deltagere" knap til at fjerne alle deltagere og nulstille session_state
    if st.button("Ryd deltagere"):
        scheduler.remove_all_participants()  # Fjern alle deltagere fra scheduler
        st.session_state.clear()  # Ryd hele session_state
        st.success("Alle deltagere er blevet fjernet.")
        st.rerun()

    # Opret en liste over medlemmer med en forklarende tekst som første element
    members_list = ["Importerede medlemmer"] + [
        f"{participant['name']} - {participant['company']} - {', '.join(participant['groups'])}"
        for participant in scheduler.participants
    ]
    
    # Vis en drop-down menu med medlemmer og en forklarende tekst som første element
    selected_member = st.selectbox("Medlemsliste", members_list)
    
    # Vis kun den valgte deltager, hvis brugeren har valgt et faktisk medlem
    # if selected_member != "Valgt medlem":
        # st.write(f"Du har valgt: {selected_member}")

    # for participant in scheduler.participants:
        # st.write(f"{participant['name']} - {participant['email']} - {participant['company']} - {', '.join(participant['groups'])}")

    # Vis shufflede grupper
    if 'shuffled_groups' in st.session_state:
        st.subheader("Shufflede mødegrupper")
        for i, group in enumerate(st.session_state.shuffled_groups, 1):
            group_members = ', '.join(participant.get('name', 'Unavngivet') for participant in group)
            st.write(f"Gruppe {i}: {group_members}")

        # Tilføj download mulighed
        st.markdown('<h3 style="color:red;">STEP 5</h3>', unsafe_allow_html=True)
        st.subheader("Download mødegrupper")
        
        if st.button("Download mødegrupper"):
            csv = scheduler.export_groups_to_csv(st.session_state.shuffled_groups)
            st.download_button(
                label="Download CSV fil",
                data=csv,
                file_name="modegrupper.csv",
                mime="text/csv"
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
