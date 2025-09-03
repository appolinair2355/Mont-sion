from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import yaml
import io
import xlsxwriter
import xlrd2
import os
import uuid
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ecole-mont-sion-fix')
PORT = int(os.environ.get('PORT', 10000))
DATABASE = 'database.yaml'

MATIERES = ['Communication écrite', 'Lecture', 'SVT', 'Anglais',
            'Histoire-Géographie', 'Espagnol', 'Mathématiques']
TRIMESTRES = ['Intero1', 'Intero2']

# ---------- BASE ----------
def load_data():
    try:
        with open(DATABASE, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {'primaire': [], 'secondaire': []}
        for niv in ['primaire', 'secondaire']:
            for s in data.setdefault(niv, []):
                s.setdefault('notes', {})
                for m in MATIERES:
                    s['notes'].setdefault(m, {'Intero1': None, 'Intero2': None})
                s.setdefault('paiements', [])
        return data
    except FileNotFoundError:
        return {'primaire': [], 'secondaire': []}

def save_data(data):
    with open(DATABASE, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

# ---------- ROUTES ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = load_data()
        nom = request.form.get('nom', '').strip().upper()
        prenoms = request.form.get('prenoms', '').strip().title()
        classe = request.form.get('classe', '')
        sexe = request.form.get('sexe', '')
        date_naissance = request.form.get('date_naissance', '')
        parent = request.form.get('parent', '').strip().title()
        phone = re.sub(r'\D', '', request.form.get('parent_phone', ''))
        frais = int(request.form.get('frais', 0))
        niveau = request.form.get('niveau', '')

        if not all([nom, prenoms, classe, sexe, date_naissance, parent, phone, frais, niveau]):
            flash('Tous les champs sont obligatoires', 'error')
            return render_template('register.html')

        data.setdefault(niveau, []).append({
            'id': str(uuid.uuid4()),
            'nom': nom, 'prenoms': prenoms, 'classe': classe, 'sexe': sexe,
            'date_naissance': date_naissance, 'parent': parent, 'parent_phone': phone,
            'frais_total': frais, 'notes': {m: {'Intero1': None, 'Intero2': None} for m in MATIERES},
            'paiements': [], 'date_inscription': datetime.now().strftime('%d/%m/%Y')
        })
        save_data(data)
        flash('Élève inscrit', 'success')
        return redirect(url_for('students'))
    return render_template('register.html')

@app.route('/students')
def students():
    data = load_data()
    all_st = data['primaire'] + data['secondaire']
    classes = sorted({s.get('classe', 'Sans classe') for s in all_st})
    grouped = {c: [s for s in all_st if s.get('classe') == c] for c in classes}
    return render_template('students.html', grouped=grouped, matieres=MATIERES)

@app.route('/edit/<sid>', methods=['GET', 'POST'])
def edit(sid):
    data = load_data()
    student = None
    for niv in ['primaire', 'secondaire']:
        student = next((s for s in data[niv] if s['id'] == sid), None)
        if student: break
    if not student:
        flash('Élève introuvable', 'error')
        return redirect(url_for('students'))
    if request.method == 'POST':
        student['nom'] = request.form.get('nom', '').strip().upper()
        student['prenoms'] = request.form.get('prenoms', '').strip().title()
        student['classe'] = request.form.get('classe', '')
        student['sexe'] = request.form.get('sexe', '')
        student['date_naissance'] = request.form.get('date_naissance', '')
        student['parent'] = request.form.get('parent', '').strip().title()
        student['parent_phone'] = re.sub(r'\D', '', request.form.get('parent_phone', ''))
        student['frais_total'] = int(request.form.get('frais_total', 0))
        save_data(data)
        flash('Élève modifié', 'success')
        return redirect(url_for('students'))
    return render_template('edit.html', student=student)

@app.route('/delete/<sid>', methods=['POST'])
def delete(sid):
    data = load_data()
    for niv in ['primaire', 'secondaire']:
        data[niv] = [s for s in data[niv] if s['id'] != sid]
    save_data(data)
    flash('Élève supprimé', 'success')
    return redirect(url_for('students'))

@app.route('/scolarite', methods=['GET', 'POST'])
def scolarite():
    data = load_data()
    students = data['primaire'] + data['secondaire']
    if request.method == 'POST':
        sid = request.form.get('student_id')
        amount = int(request.form.get('amount', 0))
        if not sid or amount <= 0:
            flash('Montant ou élève invalide', 'error')
            return redirect(url_for('scolarite'))
        for niv in ['primaire', 'secondaire']:
            for s in data[niv]:
                if s['id'] == sid:
                    s['paiements'].append({'date': datetime.now().strftime('%d/%m/%Y'),
                                           'montant': amount, 'mode': 'Espèces'})
                    save_data(data)
                    flash('Paiement enregistré', 'success')
                    return redirect(url_for('scolarite'))
    for s in students:
        s['paye'] = sum(p['montant'] for p in s.get('paiements', []))
        s['reste'] = s['frais_total'] - s['paye']
    return render_template('scolarite.html', students=students)

@app.route('/notes', methods=['GET', 'POST'])
def notes():
    data = load_data()
    students = data['primaire'] + data['secondaire']
    if request.method == 'POST':
        for s in students:
            for m in MATIERES:
                for t in TRIMESTRES:
                    val = request.form.get(f"{s['id']}_{m}_{t}", '').strip()
                    s['notes'][m][t] = float(val) if val else None
        save_data(data)
        flash('Notes sauvegardées', 'success')
        return redirect(url_for('notes'))
    return render_template('notes.html', students=students, matieres=MATIERES, trimestres=TRIMESTRES)

@app.route('/import_excel', methods=['GET', 'POST'])
def import_excel():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename.lower().endswith('.xlsx'):
            flash('Fichier .xlsx requis', 'error')
            return redirect(url_for('import_excel'))

        wb = xlrd2.open_workbook(file_contents=file.read())
        ws = wb.sheet_by_index(0)
        headers = [ws.cell_value(0, col) for col in range(ws.ncols)]
        data = load_data()

        for r in range(1, ws.nrows):
            row = ws.row_values(r)
            eleve = {
                'id': str(uuid.uuid4()),
                'nom': str(row[headers.index('Nom')]).upper(),
                'prenoms': str(row[headers.index('Prénoms')]).title(),
                'classe': str(row[headers.index('Classe')]),
                'sexe': str(row[headers.index('Sexe')]).upper(),
                'date_naissance': str(row[headers.index('DateNaissance')]),
                'parent': str(row[headers.index('Parent')]).title(),
                'parent_phone': re.sub(r'\D', '', str(row[headers.index('Téléphone')])),
                'frais_total': int(row[headers.index('FraisTotal')]),
                'notes': {m: {'Intero1': None, 'Intero2': None} for m in MATIERES},
                'paiements': []
            }
            for m in MATIERES:
                for t in TRIMESTRES:
                    key = f'{m}{t}'
                    val = row[headers.index(key)] if key in headers else None
                    eleve['notes'][m][t] = float(val) if val else None
            idx = 1
            while f'Paiement{idx}' in headers:
                val = row[headers.index(f'Paiement{idx}')]
                if val:
                    eleve['paiements'].append({'date': '', 'montant': int(val), 'mode': 'Import'})
                idx += 1
            niveau = 'primaire' if eleve['classe'] in {'CI','CP','CE1','CE2','CM1','CM2'} else 'secondaire'
            data.setdefault(niveau, []).append(eleve)
        save_data(data)
        flash('Import réussi', 'success')
        return redirect(url_for('students'))
    return render_template('import_excel.html')

@app.route('/export_excel')
def export_excel():
    data = load_data()
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = wb.add_worksheet('Élèves')
    headers = ['Nom', 'Prénoms', 'Classe', 'Sexe', 'DateNaissance', 'Parent', 'Téléphone', 'FraisTotal']
    for m in MATIERES:
        for t in TRIMESTRES:
            headers.append(f'{m}{t}')
    max_p = max([len(s.get('paiements', [])) for s in data['primaire'] + data['secondaire']], default=0)
    for i in range(1, max_p + 1):
        headers.append(f'Paiement{i}')
    headers.append('Reste')
    for col, h in enumerate(headers):
        ws.write(0, col, h)
    row = 1
    for s in data['primaire'] + data['secondaire']:
        ws.write(row, 0, s['nom'])
        ws.write(row, 1, s['prenoms'])
        ws.write(row, 2, s['classe'])
        ws.write(row, 3, s['sexe'])
        ws.write(row, 4, s['date_naissance'])
        ws.write(row, 5, s['parent'])
        ws.write(row, 6, s['parent_phone'])
        ws.write(row, 7, s['frais_total'])
        col = 8
        for m in MATIERES:
            for t in TRIMESTRES:
                ws.write(row, col, s['notes'][m][t] or '')
                col += 1
        for p in s['paiements']:
            ws.write(row, col, p['montant'])
            col += 1
        reste = s['frais_total'] - sum(p['montant'] for p in s['paiements'])
        ws.write(row, col, reste)
        row += 1
    wb.close()
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue()),
        as_attachment=True,
        download_name=f"eleves_complet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
                
