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
    st.sidebar.title("Navigation")
    
    # Erstat dropdown med knapper
    if st.sidebar.button("Hovedside >"):
        st.session_state.page = "Hovedside"
    if st.sidebar.button("Quick shuffle af mødegrupper >"):
        st.session_state.page = "Shuffle Mødegrupper"
    
    # Skjul statistik-knappen for nu (kan gøres synlig senere)
    # if st.sidebar.button("Statistik >"):
    #     st.session_state.page = "Statistik"
    
    # Tilføj horisontal linje under sidste knap
    st.sidebar.markdown("---")

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
    uploaded_file = st.file_uploader("Upload Excel eller CSV fil", type=['csv', 'xlsx', 'xls'])
    if uploaded_file is not None:
        st.markdown('<h3 style="color:red;">STEP 2</h3>', unsafe_allow_html=True)
        if st.button("Importer fra fil"):
            success, message = import_members_from_file(scheduler, uploaded_file)
            if success:
                st.success(message)
            else:
                st.error(message)

    # Datovælger for mødet
    st.markdown('<h3 style="color:red;">STEP 3</h3>', unsafe_allow_html=True)
    meeting_date = st.date_input("Vælg mødedato", value=datetime.now())
    
    # Gruppér deltagere baseret på deres gruppetilhør
    st.markdown('<h3 style="color:red;">STEP 4</h3>', unsafe_allow_html=True)
    grouped_participants = defaultdict(list)
    all_members = []
    for participant in scheduler.participants:
        name = participant.get('name', 'Unavngivet')
        all_members.append(name)
        groups = participant.get('groups', ['Ikke tildelt'])
        for group in groups:
            grouped_participants[group].append(name)

    # Identificer duplikate medlemmer
    duplicate_members = set([name for name in all_members if all_members.count(name) > 1])
    
    # Sorter grupperne og deltagerne inden for hver gruppe
    sorted_groups = sorted([g for g in grouped_participants.keys() if g != 'Ikke tildelt'])
    if 'Ikke tildelt' in grouped_participants:
        sorted_groups.append('Ikke tildelt')
    
    st.subheader("Vælg deltagere fra bruttoliste")

    # Tilføj "Ryd deltagere" knap til at fjerne alle deltagere og nulstille session_state
    if st.button("Ryd deltagere"):
        scheduler.remove_all_participants()  # Fjern alle deltagere fra scheduler
        st.session_state.clear()  # Ryd hele session_state
        st.success("Alle deltagere er blevet fjernet.")
        st.rerun()
    
    # Opret dropdown-menuer for hver gruppetilhør
    for group in sorted_groups:
        with st.expander(f"{group} ({len(grouped_participants[group])} medlemmer)"):
            all_selected = st.checkbox(f"Vælg alle i {group}", value=True, key=f"select_all_{group}")
            
            col1, col2 = st.columns(2)
            group_has_multi_members = False
            for i, name in enumerate(sorted(grouped_participants[group])):
                col = col1 if i % 2 == 0 else col2
                
                display_name = f"{name} *" if name in duplicate_members else name
                if name in duplicate_members:
                    group_has_multi_members = True
                
                if col.checkbox(display_name, key=f"checkbox_{group}_{name}", value=all_selected):
                    if 'bruttoliste' not in st.session_state:
                        st.session_state.bruttoliste = []
                    if name not in st.session_state.bruttoliste:
                        st.session_state.bruttoliste.append(name)
                elif name in st.session_state.get('bruttoliste', []):
                    st.session_state.bruttoliste.remove(name)
            
            if group_has_multi_members:
                st.write("*Dette medlem findes i flere tilhørsgrupper")

    # Opdater bruttolisten baseret på alle checkboxes
    st.session_state.bruttoliste = [
        name for group in sorted_groups 
        for name in grouped_participants[group] 
        if st.session_state.get(f"checkbox_{group}_{name}", False)
    ]

    # Vis bruttolisten i to kolonner
    st.subheader("Bruttoliste")
    # Ryd bruttoliste knap
    if st.button("Ryd bruttoliste"):
        if 'bruttoliste' in st.session_state:
            st.session_state.bruttoliste = []
        for key in list(st.session_state.keys()):
            if key.startswith("checkbox_") or key.startswith("select_all_"):
                st.session_state[key] = False
        st.rerun()
    # Brug en expander til at vise eller skjule indholdet under "Se bruttoliste"
    with st.expander("Se bruttoliste"):
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

    # STEP 5: Vælg gruppestørrelse og foreslå grupper
    st.markdown('<h3 style="color:red;">STEP 5</h3>', unsafe_allow_html=True)
    st.subheader("Foreslå grupper")
    
    col1, col2 = st.columns(2)
    with col1:
        group_size = st.selectbox("Vælg antal personer per gruppe", [3, 4, 5, 6], index=1, key="group_size")
    with col2:
        if st.button("Foreslå grupper"):
            if 'bruttoliste' in st.session_state and st.session_state.bruttoliste:
                suggested_groups, unassigned_count = scheduler.shuffle_groups(group_size)
                if suggested_groups:
                    st.session_state.suggested_groups = suggested_groups
                    st.session_state.unassigned_count = unassigned_count
                    st.success(f"Grupper er blevet foreslået. {unassigned_count} deltagere kunne ikke fordeles optimalt.")
                else:
                    st.error("Der opstod en fejl under forslag af grupper.")
            else:
                st.warning("Tilføj deltagere til bruttolisten før du foreslår grupper.")

    # Knap til at foreslå grupper
    st.markdown('<h3 style="color:red;">STEP 5</h3>', unsafe_allow_html=True)
    if st.button("Foreslå grupper"):
        if st.session_state.bruttoliste:
            suggested_groups = scheduler.suggest_groups(st.session_state.bruttoliste)
            if suggested_groups:
                st.session_state.suggested_groups = suggested_groups
                st.success("Grupper er foreslået. Du kan justere dem manuelt når mødegrupperne er oprettet.")
            else:
                st.error("For få deltagere til at foreslå grupper.")
        else:
            st.warning("Tilføj deltagere til bruttolisten før du foreslår grupper.")

    # Vis foreslåede grupper (hvis de findes)
    if 'suggested_groups' in st.session_state:
        st.subheader("Foreslåede grupper")
        for i, group in enumerate(st.session_state.suggested_groups, 1):
            group_str = f"Gruppe {i}:"
            for name in group:
                participant = next((p for p in scheduler.participants if p['name'] == name), None)
                if participant:
                    affiliations = ', '.join(participant.get('groups', ['Ikke tildelt']))
                    group_str += f" {name} ({affiliations}),"
                else:
                    group_str += f" {name} (Ukendt),"
            group_str = group_str.rstrip(',')  # Fjern det sidste komma
            st.write(group_str)
        
        if st.session_state.get('unassigned_count', 0) > 0:
            st.write(f"Antal deltagere, der ikke kunne fordeles optimalt: {st.session_state.unassigned_count}")

        # STEP 6: Opret møde med de foreslåede grupper
        st.markdown('<h3 style="color:red;">STEP 6</h3>', unsafe_allow_html=True)
        if st.button("Opret møde med disse grupper", key="create_meeting_button"):
            meeting_date = st.session_state.get('meeting_date', datetime.now().date())
            meeting_name = scheduler.create_meeting(st.session_state.suggested_groups, str(meeting_date))
            st.success(f"Møde '{meeting_name}' oprettet for {meeting_date} med de foreslåede grupper.")
            scheduler.save_data()
            del st.session_state.suggested_groups
            st.rerun()

    # Vis det seneste møde og tidligere møder
    if scheduler.meetings:
        st.header("Senest oprettet møde")
        latest_meeting = scheduler.meetings[-1]
        with st.expander(f"{latest_meeting.get('name', 'Ukendt navn')} ({latest_meeting.get('date', 'Ingen dato angivet')})", key="latest_meeting_expander"):
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
            
            if st.button("Rediger grupper for det seneste møde", key="edit_latest_meeting_button"):
                st.session_state.editing_meeting = len(scheduler.meetings) - 1
                st.session_state.manual_groups, st.session_state.unassigned = scheduler.manual_group_matching(
                    [p for group in latest_meeting['groups'] for p in group],
                    latest_meeting['groups']
                )
                st.rerun()
            
            if st.button("Slet det seneste møde", key="delete_latest_meeting_button"):
                if scheduler.delete_meeting(len(scheduler.meetings) - 1):
                    st.success("Det seneste møde er blevet slettet.")
                    st.rerun()
                else:
                    st.error("Der opstod en fejl ved sletning af mødet.")

        if len(scheduler.meetings) > 1:
            st.header("Tidligere møder")
            for meeting_index, meeting in enumerate(reversed(scheduler.meetings[:-1])):
                with st.expander(f"{meeting.get('name', 'Ukendt navn')} ({meeting.get('date', 'Ingen dato angivet')}, {sum(len(group) for group in meeting['groups'])} deltagere)", key=f"previous_meeting_expander_{meeting_index}"):
                    st.write("Grupper:")
                    for j, group in enumerate(meeting['groups']):
                        st.write(f"Gruppe {j+1}: {', '.join(group)}")
                    
                    if st.button(f"Rediger grupper", key=f"edit_meeting_button_{meeting_index}"):
                        st.session_state.editing_meeting = scheduler.meetings.index(meeting)
                        st.session_state.manual_groups, st.session_state.unassigned = scheduler.manual_group_matching(
                            [p for group in meeting['groups'] for p in group],
                            meeting['groups']
                        )
                        st.rerun()
                    
                    if st.button(f"Slet møde", key=f"delete_meeting_button_{meeting_index}"):
                        if scheduler.delete_meeting(scheduler.meetings.index(meeting)):
                            st.success(f"Mødet er blevet slettet.")
                            st.rerun()
                        else:
                            st.error("Der opstod en fejl ved sletning af mødet.")

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
