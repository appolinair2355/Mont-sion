from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import yaml
import io
import xlsxwriter
import xlrd2
import os
import uuid
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ecole-mont-sion-secret-key')

# Configuration Render.com
PORT = int(os.environ.get('PORT', 10000))
DATABASE = 'database.yaml'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configuration SMS
SMS_SENDER = '+2290167924076'

class SMSService:
    def send_sms(self, to_number, message):
        """SMS simplifié pour tests"""
        clean_number = re.sub(r'\D', '', str(to_number))
        if len(clean_number) >= 8:
            print(f"SMS envoyé à {clean_number}: {message}")
            return True
        return False

sms_service = SMSService()

def load_data():
    """Charge la base complète"""
    try:
        with open(DATABASE, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file) or {'primaire': [], 'secondaire': []}
            for niveau in ['primaire', 'secondaire']:
                for student in data.get(niveau, []):
                    if 'notes' not in student:
                        student['notes'] = {}
                    if 'paiements' not in student:
                        student['paiements'] = []
            return data
    except FileNotFoundError:
        return {'primaire': [], 'secondaire': []}

def save_data(data):
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

@app.route('/export_excel')
def export_excel():
    data = load_data()
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    # Feuille 1: Élèves
    ws1 = workbook.add_worksheet('Élèves')
    headers = ['ID', 'Nom', 'Prénoms', 'Sexe', 'Classe', 'Date naissance', 'Parent', 'Téléphone', 'Frais Total', 'Frais Payé', 'Frais Restant', 'Date inscription']
    for col, header in enumerate(headers):
        ws1.write(0, col, header)
    
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
            row += 1
    
    workbook.close()
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue()),
        as_attachment=True,
        download_name=f"export_complet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )

@app.route('/import_excel', methods=['GET', 'POST'])
def import_excel():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename.endswith('.xlsx'):
            workbook = xlrd2.open_workbook(file_contents=file.read())
            worksheet = workbook.sheet_by_index(0)
            
            data = load_data()
            for row in range(1, worksheet.nrows):
                try:
                    values = worksheet.row_values(row)
                    eleve = {
                        'id': str(uuid.uuid4()),
                        'nom': str(values[1]).upper(),
                        'prenoms': str(values[2]).title(),
                        'classe': str(values[3]),
                        'frais_total': int(float(str(values[4]))),
                        'frais_paye': 0,
                        'frais_restant': int(float(str(values[4]))),
                        'notes': {},
                        'paiements': []
                    }
                    
                    if str(values[4]).upper() in ['CI', 'CP', 'CE1', 'CE2', 'CM1', 'CM2']:
                        data['primaire'].append(eleve)
                    else:
                        data['secondaire'].append(eleve)
                except Exception as e:
                    print(f"Ligne {row} ignorée: {e}")
                    continue
            
            save_data(data)
            flash('Import réussi!', 'success')
            return redirect(url_for('students'))
    return render_template('import_excel.html')

@app.route('/pay', methods=['POST'])
def pay():
    if request.form.get('password') != 'kouame':
        flash('Mot de passe incorrect!', 'error')
        return redirect(url_for('scolarite'))
    
    student_id = request.form.get('student_id')
    amount = int(request.form.get('amount', 0))
    
    data = load_data()
    for niveau in ['primaire', 'secondaire']:
        for student in data.get(niveau, []):
            if student.get('id') == student_id:
                new_restant = max(0, student.get('frais_restant', 0) - amount)
                student['frais_paye'] += amount
                student['frais_restant'] = new_restant
                
                student['paiements'].append({
                    'date': datetime.now().strftime('%d/%m/%Y'),
                    'montant': amount
                })
                
                save_data(data)
                
                # SMS
                message = f"Vous venez de payer {amount} FCFA. Restant: {new_restant} FCFA"
                sms_service.send_sms(student['parent_phone'], message)
                
                flash('Paiement enregistré!', 'success')
                return redirect(url_for('scolarite'))
    
    return redirect(url_for('scolarite'))

@app.route('/scolarite')
def scolarite():
    data = load_data()
    students = data.get('primaire', []) + data.get('secondaire', [])
    return render_template('scolarite.html', students=students)

@app.route('/edit_delete')
def edit_delete():
    data = load_data()
    students = data.get('primaire', []) + data.get('secondaire', [])
    return render_template('edit_delete.html', students=students)

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

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
