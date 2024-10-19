import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import uuid

def update_members_from_sheet(scheduler):
    st.write("Starter import proces...")
    
    # Ryd alle eksisterende medlemmer
    scheduler.participants.clear()
    scheduler.group_affiliations.clear()
    st.write("Alle eksisterende medlemmer og gruppetilhør er fjernet.")
    
    # Genindlæs data fra Google Sheets
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
    st.write(f"Data indlæst fra Google Sheets. Antal rækker: {len(df)}")

    added_count = 0
    errors = []

    for index, row in df.iterrows():
        try:
            full_name = str(row['Navn']).strip() if pd.notnull(row['Navn']) else None
            if not full_name:
                errors.append(f"Række {index + 2} i Google Sheet har ikke et gyldigt navn.")
                continue
            
            groups = [g.strip() for g in str(row['Gruppe']).split(',') if g.strip()] if pd.notnull(row['Gruppe']) else ['Ikke tildelt']
            
            member_data = {
                "name": full_name,
                "groups": groups,
                "email": str(row['Email']).strip() if pd.notnull(row.get('Email')) else "",
                "company": str(row['Virksomhed']).strip() if pd.notnull(row.get('Virksomhed')) else "",
                "position": str(row['Stilling']).strip() if pd.notnull(row.get('Stilling')) else "",
                "industry": str(row['Branche']).strip() if pd.notnull(row.get('Branche')) else ""
            }
            
            scheduler.add_participant(full_name, member_data)
            added_count += 1
            
            for group in groups:
                scheduler.add_group_affiliation(group)
        
        except Exception as e:
            errors.append(f"Fejl ved behandling af række {index + 2}: {str(e)}")

    st.write(f"Antal medlemmer efter import: {len(scheduler.participants)}")
    
    scheduler.save_data()

    status_message = f"Tilføjede {added_count} medlemmer."
    if errors:
        status_message += f" Der opstod {len(errors)} fejl under opdateringen."
    
    return True, status_message

def export_meetings_to_sheets(scheduler):
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Læs eksisterende data
    existing_data = conn.read(worksheet="Mødedata")
    
    # Konverter scheduler.meetings til en dataframe
    new_meetings = scheduler.export_meetings_to_dataframe()
    
    # Check om 'Møde-ID' eller 'serial' kolonnen eksisterer
    id_column = 'Møde-ID' if 'Møde-ID' in new_meetings.columns else 'serial'
    
    if id_column not in new_meetings.columns:
        return False, "Fejl: Kunne ikke finde møde-id kolonne i dataen."
    
    # Håndter eksisterende ID'er mere sikkert
    if id_column in existing_data.columns:
        existing_ids = set(existing_data[id_column].dropna().astype(str).tolist())
    else:
        existing_ids = set()
    
    # Konverter nye møde-ID'er til strenge for sammenligning
    new_meetings[id_column] = new_meetings[id_column].astype(str)
    
    # Filtrer nye møder, der ikke allerede er i sheetet
    new_meetings = new_meetings[~new_meetings[id_column].isin(existing_ids)]
    
    if new_meetings.empty:
        return True, "Ingen nye møder at eksportere."
    
    try:
        # Tilføj nye møder til eksisterende data
        updated_data = pd.concat([existing_data, new_meetings], ignore_index=True)
        
        # Opdater Google Sheet
        conn.update(data=updated_data, worksheet="Mødedata")
        
        return True, f"Eksporterede {len(new_meetings)} nye møder til Google Sheets."
    except Exception as e:
        return False, f"Der opstod en fejl under eksport af data: {str(e)}"

# Helper function to convert DataFrame to dict for JSON serialization
def df_to_dict(df):
    return df.to_dict(orient='records')

# Helper function to convert dict back to DataFrame
def dict_to_df(data):
    return pd.DataFrame(data)

def import_members_from_file(scheduler, file):
    if file is not None:
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file)
            else:
                return False, "Ugyldigt filformat. Brug venligst CSV eller Excel."
            
            # Ryd eksisterende data
            scheduler.participants.clear()
            scheduler.group_affiliations.clear()
            
            # Importer data fra filen
            for index, row in df.iterrows():
                full_name = str(row['Navn']).strip() if pd.notnull(row['Navn']) else None
                if not full_name:
                    continue
                
                groups = [g.strip() for g in str(row['Gruppe']).split(',') if g.strip()] if pd.notnull(row['Gruppe']) else ['Ikke tildelt']
                
                member_data = {
                    "name": full_name,
                    "groups": groups,
                    "email": str(row['Email']).strip() if pd.notnull(row.get('Email')) else "",
                    "company": str(row['Virksomhed']).strip() if pd.notnull(row.get('Virksomhed')) else "",
                    "position": str(row['Stilling']).strip() if pd.notnull(row.get('Stilling')) else "",
                    "industry": str(row['Branche']).strip() if pd.notnull(row.get('Branche')) else ""
                }
                
                scheduler.add_participant(full_name, member_data)
                
                for group in groups:
                    scheduler.add_group_affiliation(group)
            
            scheduler.save_data()
            return True, f"Importerede {len(scheduler.participants)} medlemmer fra filen."
        except Exception as e:
            return False, f"Fejl under import af fil: {str(e)}"
    else:
        return False, "Ingen fil valgt."
