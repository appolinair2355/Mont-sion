from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import yaml
import io
import xlsxwriter
import xlrd2
import os
import uuid
from datetime import datetime
import urllib.request
import json
import re

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ecole-mont-sion-secret-key-2024')

# Configuration pour Render.com
PORT = int(os.environ.get('PORT', 10000))
DATABASE = 'database.yaml'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configuration SMS
SMS_GATEWAY_URL = os.environ.get('SMS_GATEWAY_URL', 'http://localhost:8082/send')
SMS_TOKEN = os.environ.get('SMS_TOKEN', '7f69129b-7010-44d7-965d-603cec01b895')
SMS_SENDER = os.environ.get('SMS_SENDER', '+2290167924076')

class SMSService:
    def send_sms(self, to_number, message):
        """Envoi SMS avec votre numéro"""
        try:
            clean_number = re.sub(r'\D', '', str(to_number))
            if len(clean_number) >= 8:
                payload = {
                    "to": f"+229{clean_number[-10:]}",
                    "from": SMS_SENDER,
                    "message": message
                }
                
                data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(SMS_GATEWAY_URL, data=data)
                req.add_header('Content-Type', 'application/json')
                req.add_header('Authorization', f'Bearer {SMS_TOKEN}')
                
                response = urllib.request.urlopen(req)
                return response.getcode() == 200
        except Exception as e:
            print(f"SMS Error: {e}")
            return False

sms_service = SMSService()

def load_data():
    """Charge la base de données complète"""
    try:
        with open(DATABASE, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file) or {'primaire': [], 'secondaire': []}
            # Assurer la structure complète
            for niveau in ['primaire', 'secondaire']:
                for student in data.get(niveau, []):
                    if 'notes' not in student:
                        student['notes'] = {}
                    if 'paiements' not in student:
                        student['paiements'] = []
                    if 'frais_total' not in student:
                        student['frais_total'] = student.get('frais_scolarite', 0)
                    if 'frais_paye' not in student:
                        student['frais_paye'] = 0
                    if 'frais_restant' not in student:
                        student['frais_restant'] = student.get('frais_scolarite', 0)
            return data
    except FileNotFoundError:
        initial = {
            'primaire': [],
            'secondaire': []
        }
        save_data(initial)
        return initial

def save_data(data):
    """Sauvegarde complète"""
    with open(DATABASE, 'w', encoding='utf-8') as file:
        yaml.dump(data, file, allow_unicode=True, default_flow_style=False)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = load_data()
        
        eleve = {
            'id': str(uuid.uuid4()),
            'nom': request.form['nom'].strip().upper(),
            'prenoms': request.form['prenoms'].strip().title(),
            'classe': request.form['classe'],
            'sexe': request.form['sexe'].upper(),
            'date_naissance': request.form['date_naissance'],
            'parent': request.form['parent'].strip().title(),
            'parent_phone': re.sub(r'\D', '', request.form['parent_phone']),
            'frais_total': int(request.form['frais']),
            'frais_paye': 0,
            'frais_restant': int(request.form['frais']),
            'date_inscription': datetime.now().strftime('%d/%m/%Y'),
            'notes': {},
            'paiements': []
        }
        
        data[request.form['niveau']].append(eleve)
        save_data(data)
        flash('Élève inscrit avec succès!', 'success')
        return redirect(url_for('students'))
    
    return render_template('register.html')

@app.route('/students')
def students():
    data = load_data()
    students = data.get('primaire', []) + data.get('secondaire', [])
    
    if not students:
        return render_template('students.html', grouped={})
    
    classes = sorted(set(s.get('classe', 'Sans classe') for s in students))
    grouped = {cls: [s for s in students if s.get('classe') == cls] for cls in classes}
    
    return render_template('students.html', grouped=grouped)

@app.route('/notes')
def notes():
    data = load_data()
    students = data.get('primaire', []) + data.get('secondaire', [])
    matieres = ['Mathématiques', 'Français', 'Anglais', 'Histoire', 'Géographie', 'Sciences', 'SVT', 'Physique', 'Chimie']
    
    return render_template('notes.html', students=students, matieres=matieres)

@app.route('/add_note', methods=['POST'])
def add_note():
    data = load_data()
    student_id = request.form.get('student_id')
    matiere = request.form.get('matiere')
    note = float(request.form.get('note', 0))
    
    for niveau in ['primaire', 'secondaire']:
        for student in data.get(niveau, []):
            if student.get('id') == student_id:
                student['notes'][matiere] = note
                save_data(data)
                flash('Note ajoutée!', 'success')
                return redirect(url_for('notes'))
    
    flash('Erreur!', 'error')
    return redirect(url_for('notes'))

@app.route('/export_excel')
def export_excel():
    """Export complet : élèves, notes, paiements, scolarité"""
    try:
        data = load_data()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Feuille 1 : Informations élèves
        ws1 = workbook.add_worksheet('Élèves')
        headers1 = [
            'ID', 'Nom', 'Prénoms', 'Sexe', 'Classe', 'Date de naissance',
            'Parent/Tuteur', 'Téléphone', 'Frais Total', 'Frais Payé',
            'Frais Restant', 'Date inscription', 'Niveau'
        ]
        
        header_format = workbook.add_format({'bold': True, 'bg_color': '#4472C4', 'font_color': 'white'})
        
        for col, header in enumerate(headers1):
            ws1.write(0, col, header, header_format)
        
        row = 1
        for niveau in ['primaire', 'secondaire']:
            for student in data.get(niveau, []):
                ws1.write(row, 0, student.get('id', ''))
                ws1.write(row, 1, student.get('nom', ''))
                ws1.write(row, 2, student.get('prenoms', ''))
                ws1.write(row, 3, student.get('sexe', ''))
                ws1.write(row, 4, student.get('classe', ''))
                ws1.write(row, 5, student.get('date_naissance', ''))
                ws1.write(row, 6, student.get('parent', ''))
                ws1.write(row, 7, student.get('parent_phone', ''))
                ws1.write(row, 8, student.get('frais_total', 0))
                ws1.write(row, 9, student.get('frais_paye', 0))
                ws1.write(row, 10, student.get('frais_restant', 0))
                ws1.write(row, 11, student.get('date_inscription', ''))
                ws1.write(row, 12, niveau.title())
                row += 1
        
        # Feuille 2 : Notes détaillées
        ws2 = workbook.add_worksheet('Notes')
        headers2 = ['ID Élève', 'Nom', 'Prénoms', 'Classe', 'Matière', 'Note']
        for col, header in enumerate(headers2):
            ws2.write(0, col, header, header_format)
        
        row2 = 1
        for niveau in ['primaire', 'secondaire']:
            for student in data.get(niveau, []):
                for matiere, note in student.get('notes', {}).items():
                    ws2.write(row2, 0, student.get('id', ''))
                    ws2.write(row2, 1, student.get('nom', ''))
                    ws2.write(row2, 2, student.get('prenoms', ''))
                    ws2.write(row2, 3, student.get('classe', ''))
                    ws2.write(row2, 4, matiere)
                    ws2.write(row2, 5, note)
                    row2 += 1
        
        # Feuille 3 : Paiements
        ws3 = workbook.add_worksheet('Paiements')
        headers3 = ['ID Élève', 'Nom', 'Prenoms', 'Classe', 'Date', 'Montant', 'Mode']
        for col, header in enumerate(headers3):
            ws3.write(0, col, header, header_format)
        
        row3 = 1
        for niveau in ['primaire', 'secondaire']:
            for student in data.get(niveau, []):
                for paiement in student.get('paiements', []):
                    ws3.write(row3, 0, student.get('id', ''))
                    ws3.write(row3, 1, student.get('nom', ''))
                    ws3.write(row3, 2, student.get('prenoms', ''))
                    ws3.write(row3, 3, student.get('classe', ''))
                    ws3.write(row3, 4, paiement.get('date', ''))
                    ws3.write(row3, 5, paiement.get('montant', 0))
                    ws3.write(row3, 6, paiement.get('mode', ''))
                    row3 += 1
        
        for sheet in [ws1, ws2, ws3]:
            for col in range(sheet.dim_colmax):
                sheet.set_column(col, col, 15)
        
        workbook.close()
        output.seek(0)
        filename = f"export_complet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            io.BytesIO(output.getvalue()),
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash('Erreur export: ' + str(e), 'error')
        return redirect(url_for('students'))

@app.route('/import_excel', methods=['GET', 'POST'])
def import_excel():
    """Import complet avec toutes les données"""
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename.endswith('.xlsx'):
            flash('Fichier .xlsx requis!', 'error')
            return redirect(url_for('import_excel'))
        
        try:
            workbook = xlrd2.open_workbook(file_contents=file.read())
            
            # Lecture des 3 feuilles
            try:
                ws_eleves = workbook.sheet_by_name('Élèves')
                ws_notes = workbook.sheet_by_name('Notes')
                ws_paiements = workbook.sheet_by_name('Paiements')
            except:
                ws_eleves = workbook.sheet_by_index(0)
                ws_notes = workbook.sheet_by_index(1) if workbook.nsheets > 1 else None
                ws_paiements = workbook.sheet_by_index(2) if workbook.nsheets > 2 else None
            
            new_data = {'primaire': [], 'secondaire': []}
            
            # Feuille Élèves
            for row in range(1, ws_eleves.nrows):
                try:
                    values = ws_eleves.row_values(row)
                    eleve = {
                        'id': str(values[0]) if str(values[0]) else str(uuid.uuid4()),
                        'nom': str(values[1]).upper(),
                        'prenoms': str(values[2]).title(),
                        'sexe': str(values[3]).upper(),
                        'classe': str(values[4]),
                        'date_naissance': str(values[5]),
                        'parent': str(values[6]).title(),
                        'parent_phone': str(values[7]),
                        'frais_total': int(float(str(values[8]))),
                        'frais_paye': int(float(str(values[9]))),
                        'frais_restant': int(float(str(values[10]))),
                        'date_inscription': str(values[11]),
                        'notes': {},
                        'paiements': []
                    }
                    
                    niveau = str(values[12]).lower()
                    if niveau == 'primaire':
                        new_data['primaire'].append(eleve)
                    else:
                        new_data['secondaire'].append(eleve)
                        
                except Exception as e:
                    print(f"Ligne {row} ignorée: {e}")
                    continue
            
            # Feuille Notes
            if ws_notes:
                for row in range(1, ws_notes.nrows):
                    try:
                        values = ws_notes.row_values(row)
                        student_id = str(values[0])
                        matiere = str(values[4])
                        note = float(str(values[5]))
                        
                        for student in new_data['primaire'] + new_data['secondaire']:
                            if student['id'] == student_id:
                                student['notes'][matiere] = note
                                break
                                
                    except Exception:
                        continue
            
            # Feuille Paiements
            if ws_paiements:
                for row in range(1, ws_paiements.nrows):
                    try:
                        values = ws_paiements.row_values(row)
                        student_id = str(values[0])
                        paiement = {
                            'date': str(values[4]),
                            'montant': int(float(str(values[5]))),
                            'mode': str(values[6])
                        }
                        
                        for student in new_data['primaire'] + new_data['secondaire']:
                            if student['id'] == student_id:
                                student['paiements'].append(paiement)
                                break
                                
                    except Exception:
                        continue
            
            save_data(new_data)
            flash(f'Import réussi! {len(new_data["primaire"]) + len(new_data["secondaire"])} élèves importés.', 'success')
            return redirect(url_for('students'))
            
        except Exception as e:
            flash(f'Erreur import: {str(e)}', 'error')
    
    return render_template('import_excel.html')

# Routes restantes (inchangées)
@app.route('/scolarite')
def scolarite():
    data = load_data()
    students = data.get('primaire', []) + data.get('secondaire', [])
    return render_template('scolarite.html', students=students)

@app.route('/notes')
def notes():
    data = load_data()
    students = data.get('primaire', []) + data.get('secondaire', [])
    matieres = ['Mathématiques', 'Français', 'Anglais', 'Histoire', 'Géographie', 'Sciences', 'SVT', 'Physique', 'Chimie']
    return render_template('notes.html', students=students, matieres=matieres)

@app.route('/edit_delete')
def edit_delete():
    data = load_data()
    students = data.get('primaire', []) + data.get('secondaire', [])
    return render_template('edit_delete.html', students=students)

@app.route('/delete/<student_id>', methods=['POST'])
def delete_student(student_id):
    if request.form.get('password') != 'arrow':
        flash('Mot de passe incorrect!', 'error')
        return redirect(url_for('edit_delete'))
    
    data = load_data()
    for niveau in ['primaire', 'secondaire']:
        data[niveau] = [s for s in data.get(niveau, []) if s.get('id') != student_id]
    
    save_data(data)
    flash('Élève supprimé!', 'success')
    return redirect(url_for('edit_delete'))

@app.route('/edit/<student_id>')
def edit_student(student_id):
    data = load_data()
    student = None
    for niveau in ['primaire', 'secondaire']:
        for s in data.get(niveau, []):
            if s.get('id') == student_id:
                student = s
                break
    return render_template('edit.html', student=student) if student else redirect(url_for('edit_delete'))

@app.route('/update/<student_id>', methods=['POST'])
def update_student(student_id):
    data = load_data()
    for niveau in ['primaire', 'secondaire']:
        for student in data.get(niveau, []):
            if student.get('id') == student_id:
                student['nom'] = request.form['nom'].upper()
                student['prenoms'] = request.form['prenoms'].title()
                student['classe'] = request.form['classe']
                student['sexe'] = request.form['sexe']
                student['date_naissance'] = request.form['date_naissance']
                student['parent'] = request.form['parent'].title()
                student['parent_phone'] = re.sub(r'\D', '', request.form['parent_phone'])
                student['frais_total'] = int(request.form['frais_total'])
                save_data(data)
                flash('Mis à jour!', 'success')
                return redirect(url_for('students'))
    
    return redirect(url_for('edit_delete'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
