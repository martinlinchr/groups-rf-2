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
                self.ensure_meeting_numbers()  # Kald denne metode efter indlæsning af data
        else:
            self.save_data()

    def save_data(self):
        data = {
            "participants": self.participants,
            "meetings": self.meetings,
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

    def create_meeting(self, groups, date, meeting_number=None):
        self.last_meeting_serial += 1
        formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d. %B %Y")
        
        if meeting_number is None:
            meeting_number = self.last_meeting_serial
        
        meeting_name = f"Møde {meeting_number} - {formatted_date}"
        
        self.meetings.append({
            'serial': self.last_meeting_serial,
            'name': meeting_name,
            'date': date,
            'formatted_date': formatted_date,
            'meeting_number': meeting_number,
            'groups': [[p if isinstance(p, str) else p.get('name', 'Unavngivet') for p in group] for group in groups]
        })
        self.update_groupings(groups)
        self.save_data()
        
        return meeting_name

    def reset_meeting_numbers(self):
        for i, meeting in enumerate(self.meetings, 1):
            meeting['meeting_number'] = i
            meeting['name'] = f"Møde {i} - {meeting['formatted_date']}"
        self.save_data()

    def ensure_meeting_numbers(self):
        for i, meeting in enumerate(self.meetings, 1):
            if 'meeting_number' not in meeting:
                meeting['meeting_number'] = i
            if 'formatted_date' not in meeting:
                formatted_date = datetime.strptime(meeting['date'], "%Y-%m-%d").strftime("%d. %B %Y")
                meeting['formatted_date'] = formatted_date
            meeting['name'] = f"Møde {meeting['meeting_number']} - {meeting['formatted_date']}"
        self.save_data()

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
                            'Møde-ID': str(meeting.get('serial', '')),
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
        group_affiliations = defaultdict(set)

        while participants:
            group = []
            for _ in range(group_size):
                if not participants:
                    break
                
                best_participant = None
                min_conflicts = float('inf')
                
                for participant in participants:
                    participant_data = next((p for p in self.participants if p['name'] == participant), None)
                    if not participant_data:
                        continue

                    participant_affiliations = set(participant_data.get('groups', ['Ikke tildelt']))
                    conflicts = len(participant_affiliations.intersection(group_affiliations[len(groups)]))
                    
                    if conflicts < min_conflicts:
                        min_conflicts = conflicts
                        best_participant = participant

                if best_participant:
                    group.append(best_participant)
                    participants.remove(best_participant)
                    participant_data = next((p for p in self.participants if p['name'] == best_participant), None)
                    group_affiliations[len(groups)].update(participant_data.get('groups', ['Ikke tildelt']))

            if len(group) >= 3:
                groups.append(group)
            elif groups and len(groups[-1]) + len(group) <= group_size + 1:
                groups[-1].extend(group)
            else:
                # Distribute remaining participants to existing groups
                for participant in group:
                    min_group = min(groups, key=len)
                    min_group.append(participant)

        return groups, 0  # Return 0 for unassigned as we've distributed all participants

    def export_meeting_to_csv(self, meeting):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Gruppe', 'Navn', 'Email', 'Virksomhed', 'Tilhørsgruppe'])
        
        for i, group in enumerate(meeting['groups'], 1):
            for participant_name in group:
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
