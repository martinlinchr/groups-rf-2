import random
import json
import os
from datetime import datetime
import pandas as pd
import csv
import io
from config import DATA_FILE
import uuid
from collections import defaultdict

class InteractiveGroupScheduler:
    def __init__(self):
        self.participants = []
        self.meetings = []
        self.group_affiliations = set()
        self.last_meeting_serial = 0
        self.group_history = {}
        self.load_data()

    def load_data(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                self.participants = self.convert_participants(data.get("participants", []))
                self.meetings = data.get("meetings", [])
                self.group_affiliations = set(data.get("group_affiliations", []))
                self.last_meeting_serial = data.get("last_meeting_serial", 0)
                self.group_history = data.get("group_history", {})
        else:
            self.save_data()

    def save_data(self):
        data = {
            "participants": self.participants,
            "meetings": self.meetings,  # sørg for at møder også gemmes her
            "group_affiliations": list(self.group_affiliations),
            "last_meeting_serial": self.last_meeting_serial,
            "group_history": self.group_history
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)

    def convert_participants(self, participants_data):
        if isinstance(participants_data, dict):
            return [{"id": str(uuid.uuid4()), "name": name, **data} for name, data in participants_data.items()]
        elif isinstance(participants_data, list):
            return [{"id": p.get("id", str(uuid.uuid4())), **p} for p in participants_data]
        else:
            return []

    def add_group_affiliation(self, group):
        if group and group not in self.group_affiliations:
            self.group_affiliations.add(group)
            self.save_data()
            return True
        return False

    def add_participant(self, name, data):
        data['id'] = str(uuid.uuid4())
        self.participants.append(data)
        for group in data.get('groups', []):
            self.add_group_affiliation(group)
        self.save_data()
        return True

    def update_participant(self, participant_id, data):
        for i, participant in enumerate(self.participants):
            if participant['id'] == participant_id:
                self.participants[i] = data
                for group in data.get('groups', []):
                    self.add_group_affiliation(group)
                self.save_data()
                return True
        return False

    def remove_participant(self, participant_id):
        self.participants = [p for p in self.participants if p['id'] != participant_id]
        self.save_data()
        return True

    def remove_all_participants(self):
        self.participants.clear()
        self.meetings.clear()
        self.save_data()

    def suggest_groups(self, participants):
        if len(participants) < 3:
            return []

        weights = self.calculate_grouping_weights(participants)
        
        random.shuffle(participants)
        participants.sort(key=lambda x: weights.get(x, 0))
        
        total_participants = len(participants)
        base_group_size = 4
        num_groups = total_participants // base_group_size
        remainder = total_participants % base_group_size

        groups = [[] for _ in range(num_groups)]
        
        for i, participant in enumerate(participants):
            groups[i % num_groups].append(participant)
        
        if remainder == 1:
            groups[-1].append(participants[-1])
        elif remainder == 2:
            groups.append(participants[-3:])
            groups[-2].pop()
        elif remainder == 3:
            groups.append(participants[-3:])
        
        return groups

    def calculate_grouping_weights(self, participants):
        weights = defaultdict(float)
        for participant in participants:
            participant_data = next((p for p in self.participants if p['name'] == participant), None)
            if participant_data:
                groupings = participant_data.get('groupings', {})
                total_groupings = sum(groupings.values())
                for other, count in groupings.items():
                    if other in participants:
                        weights[participant] += count / total_groupings if total_groupings else 0
        return weights

    def create_meeting(self, groups, date):
        self.last_meeting_serial += 1
        meeting_name = f"Møde - {date}"  # Removed the meeting serial from the name
        
        self.meetings.append({
            'serial': self.last_meeting_serial,  # Still keep serial for internal use
            'name': meeting_name,
            'date': date,
            'groups': [[p if isinstance(p, str) else p.get('name', 'Unavngivet') for p in group] for group in groups]
        })
        self.update_groupings(groups)
        self.save_data()
        
        return meeting_name

    def update_groupings(self, groups):
        for group in groups:
            for participant in group:
                participant_data = next((p for p in self.participants if p['name'] == participant), None)
                if participant_data:
                    if 'groupings' not in participant_data:
                        participant_data['groupings'] = {}
                    for other in group:
                        if participant != other:
                            participant_data['groupings'][other] = participant_data['groupings'].get(other, 0) + 1

    def update_meeting_date(self, index, new_date):
        if 0 <= index < len(self.meetings):
            self.meetings[index]["date"] = new_date
            self.save_data()
            return True
        return False

    def delete_meeting(self, index):
        if 0 <= index < len(self.meetings):
            deleted_meeting = self.meetings.pop(index)
            for group in deleted_meeting['groups']:
                for participant_name in group:
                    participant = next((p for p in self.participants if p['name'] == participant_name), None)
                    if participant:
                        participant['meetings'] = max(0, participant.get('meetings', 0) - 1)
            self.save_data()
            return True
        return False

    def get_participation_stats(self):
        return {participant['name']: participant.get("meetings", 0) for participant in self.participants}

    def get_grouping_stats(self, participant_name):
        participant = next((p for p in self.participants if p['name'] == participant_name), None)
        if participant:
            return participant.get("groupings", {})
        return {}

    def manual_group_matching(self, attendees, existing_groups=None):
        if existing_groups is None:
            groups = [[] for _ in range((len(attendees) + 3) // 4)]
        else:
            groups = existing_groups
        
        assigned_participants = set([p for group in groups for p in group])
        unassigned = [p for p in attendees if p not in assigned_participants]
        
        return groups, unassigned

    def update_meeting_groups(self, meeting_index, new_groups):
        if 0 <= meeting_index < len(self.meetings):
            self.meetings[meeting_index]["groups"] = new_groups
            self.update_groupings(new_groups)
            self.save_data()
            return True
        return False

    def export_meetings_to_dataframe(self):
        meetings_data = []
        for meeting in self.meetings:
            date = meeting['date']
            if isinstance(date, str):
                try:
                    date = datetime.strptime(date, "%Y-%m-%d").date()
                except ValueError:
                    pass
            for group_index, group in enumerate(meeting['groups'], 1):
                for participant in group:
                    participant_data = next((p for p in self.participants if p['name'] == participant), None)
                    if participant_data:
                        affiliations = ', '.join(participant_data.get('groups', ['Ikke tildelt']))
                        meetings_data.append({
                            'Møde-ID': str(meeting.get('serial', '')),  # Ensure 'serial' is always a string
                            'Mødenavn': meeting.get('name', ''),
                            'Dato': date,
                            'Gruppe': f"Gruppe {group_index}",
                            'Deltager': participant,
                            'Tilhørsgruppe': affiliations
                        })

        return pd.DataFrame(meetings_data)

    def shuffle_groups(self, group_size):
        participants = [p['name'] for p in self.participants]
        random.shuffle(participants)

        groups = []
        unassigned = []
        group_affiliations = defaultdict(set)

        for participant in participants:
            participant_data = next((p for p in self.participants if p['name'] == participant), None)
            if not participant_data:
                continue

            participant_affiliations = set(participant_data.get('groups', ['Ikke tildelt']))

            # Find the best group to place the participant
            best_group = None
            min_conflicts = float('inf')
            for i, group in enumerate(groups):
                if len(group) < group_size:
                    conflicts = len(participant_affiliations.intersection(group_affiliations[i]))
                    if conflicts < min_conflicts or (conflicts == min_conflicts and len(group) < len(groups[best_group]) if best_group is not None else True):
                        min_conflicts = conflicts
                        best_group = i

            if best_group is not None:
                groups[best_group].append(participant)
                group_affiliations[best_group].update(participant_affiliations)
            elif len(groups) * group_size < len(participants):
                groups.append([participant])
                group_affiliations[len(groups) - 1] = participant_affiliations
            else:
                unassigned.append(participant)

        # Assign unassigned participants
        for participant in unassigned:
            participant_data = next((p for p in self.participants if p['name'] == participant), None)
            if not participant_data:
                continue

            participant_affiliations = set(participant_data.get('groups', ['Ikke tildelt']))

            best_group = None
            min_conflicts = float('inf')
            for i, group in enumerate(groups):
                conflicts = len(participant_affiliations.intersection(group_affiliations[i]))
                if conflicts < min_conflicts or (conflicts == min_conflicts and (best_group is None or len(group) < len(groups[best_group]))):
                    min_conflicts = conflicts
                    best_group = i

            if best_group is not None:
                groups[best_group].append(participant)
                group_affiliations[best_group].update(participant_affiliations)

        return groups, len(unassigned)

    def can_group_with(self, participant1, participant2):
        groupings1 = participant1.get('groupings', {})
        name2 = participant2.get('name', '')
        return name2 not in groupings1

    def save_shuffled_groups(self, groups, date):
        self.create_meeting(groups, date)
        for group in groups:
            self.update_groupings(group)
        self.save_data()

    def export_groups_to_csv(self, groups):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Gruppe', 'Navn', 'Email', 'Virksomhed', 'Tilhørsgruppe'])
        
        for i, group in enumerate(groups, 1):
            for participant in group:
                participant_name = participant if isinstance(participant, str) else participant.get('name', 'Unavngivet')
                participant_data = next((p for p in self.participants if p['name'] == participant_name), None)
                if participant_data:
                    writer.writerow([
                        f'Gruppe {i}',
                        participant_name,
                        participant_data.get('email', 'Ikke angivet'),
                        participant_data.get('company', 'Ikke angivet'),
                        ', '.join(participant_data.get('groups', ['Ikke tildelt']))
                    ])
        
        return output.getvalue()

# Importing InteractiveGroupScheduler class from scheduler
from scheduler import InteractiveGroupScheduler

# Initialize Streamlit to create an interactive app
def main():
    # Setting up the InteractiveGroupScheduler instance
    scheduler = InteractiveGroupScheduler()

    # Title for the Streamlit app
    st.title("Interactive Group Scheduler")

    # Menu for different functionalities in the app
    menu = ["Add Participant", "Create Meeting", "View Participants", "Export Data"]
    choice = st.sidebar.selectbox("Select Action", menu)

    # Add Participant functionality
    if choice == "Add Participant":
        st.subheader("Add a new participant")
        name = st.text_input("Participant Name")
        email = st.text_input("Email")
        company = st.text_input("Company")
        groups = st.text_input("Groups (comma separated)").split(',')

        if st.button("Add Participant"):
            if name:
                data = {
                    'name': name,
                    'email': email,
                    'company': company,
                    'groups': [group.strip() for group in groups if group.strip()]
                }
                scheduler.add_participant(name, data)
                st.success(f"Participant {name} added successfully!")
            else:
                st.warning("Please enter a name for the participant.")

    # Create Meeting functionality
    elif choice == "Create Meeting":
        st.subheader("Create a new meeting")
        participants = [p['name'] for p in scheduler.participants]
        selected_participants = st.multiselect("Select participants for the meeting", participants)
        meeting_date = st.date_input("Select Meeting Date")

        if st.button("Create Meeting"):
            if len(selected_participants) >= 3:
                groups = scheduler.suggest_groups(selected_participants)
                meeting_name = scheduler.create_meeting(groups, str(meeting_date))
                st.success(f"Meeting '{meeting_name}' created successfully!")
            else:
                st.warning("Please select at least 3 participants for a meeting.")

    # View Participants functionality
    elif choice == "View Participants":
        st.subheader("List of Participants")
        participants = scheduler.participants
        if participants:
            for participant in participants:
                st.write(f"Name: {participant['name']}, Email: {participant.get('email', 'N/A')}, Company: {participant.get('company', 'N/A')}")
        else:
            st.info("No participants available.")

    # Export Data functionality
    elif choice == "Export Data":
        st.subheader("Export Meetings to CSV")
        meetings_df = scheduler.export_meetings_to_dataframe()
        st.dataframe(meetings_df)

        if st.button("Export to CSV"):
            csv_data = meetings_df.to_csv(index=False).encode('utf-8')
            st.download_button(label="Download CSV", data=csv_data, file_name='meetings.csv', mime='text/csv')

if __name__ == "__main__":
    import streamlit as st
    main()
